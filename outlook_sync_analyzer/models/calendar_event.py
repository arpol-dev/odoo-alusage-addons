# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    # Champs pour l'analyse
    sync_analysis_state = fields.Selection([
        ('ok', 'OK'),
        ('stuck', 'Bloqué'),
        ('old', 'Ancien'),
        ('extreme_future', 'Futur extrême'),
        ('no_email', 'Sans email'),
    ], string='État analyse sync', compute='_compute_sync_analysis_state', store=True)

    sync_stuck_days = fields.Integer('Jours bloqué', compute='_compute_sync_stuck_days', store=True)

    @api.depends('need_sync_m', 'write_date')
    def _compute_sync_analysis_state(self):
        ICP = self.env['ir.config_parameter'].sudo()
        future_limit = int(ICP.get_param('outlook_sync_analyzer.future_year_limit', 2030))
        old_limit_days = int(ICP.get_param('outlook_sync_analyzer.old_event_limit_days', 365))

        from datetime import datetime, timedelta
        old_limit = datetime.now() - timedelta(days=old_limit_days)

        for event in self:
            if event.need_sync_m:
                # Vérifie combien de temps il est bloqué
                days_stuck = (fields.Datetime.now() - event.write_date).days if event.write_date else 0
                if days_stuck > 7:
                    event.sync_analysis_state = 'stuck'
                    continue

            if event.stop and event.stop.year > future_limit:
                event.sync_analysis_state = 'extreme_future'
            elif event.start and event.start < old_limit:
                event.sync_analysis_state = 'old'
            elif any(not att.email for att in event.attendee_ids):
                event.sync_analysis_state = 'no_email'
            else:
                event.sync_analysis_state = 'ok'

    @api.depends('need_sync_m', 'write_date')
    def _compute_sync_stuck_days(self):
        for event in self:
            if event.need_sync_m and event.write_date:
                event.sync_stuck_days = (fields.Datetime.now() - event.write_date).days
            else:
                event.sync_stuck_days = 0

    def action_analyze_need_sync(self):
        """Action pour analyser les événements need_sync_m"""
        stuck_events = self.search([
            ('need_sync_m', '=', True),
            ('write_date', '<', fields.Datetime.subtract(fields.Datetime.now(), days=7)),
        ])

        report_lines = [
            f"# Analyse des événements need_sync_m bloqués",
            f"",
            f"**Date:** {fields.Datetime.now()}",
            f"**Nombre total:** {len(stuck_events)}",
            f"",
            f"## Événements par utilisateur",
            f"",
        ]

        # Groupe par utilisateur
        events_by_user = {}
        for event in stuck_events:
            user = event.user_id or self.env['res.users']
            if user not in events_by_user:
                events_by_user[user] = []
            events_by_user[user].append(event)

        for user, events in events_by_user.items():
            report_lines.append(f"### {user.name} ({user.login})")
            report_lines.append(f"")
            report_lines.append(f"Nombre: {len(events)}")
            report_lines.append(f"")
            report_lines.append(f"| Événement | Date | Jours bloqué | Microsoft ID |")
            report_lines.append(f"|-----------|------|--------------|--------------|")
            for event in events[:20]:  # Limite à 20 par utilisateur
                days = (fields.Datetime.now() - event.write_date).days
                report_lines.append(
                    f"| {event.name} | {event.start} | {days} | {event.microsoft_id or 'N/A'} |"
                )
            if len(events) > 20:
                report_lines.append(f"| ... et {len(events) - 20} autres | | | |")
            report_lines.append(f"")

        report_content = '\n'.join(report_lines)

        # Crée un rapport
        self.env['microsoft.sync.report'].create({
            'log_id': self.env['microsoft.sync.log'].create({
                'user_id': self.env.user.id,
                'operation': 'error',
                'status': 'partial',
                'has_anomaly': True,
                'anomaly_type': 'stuck_need_sync',
                'events_count': len(stuck_events),
            }).id,
            'user_id': self.env.user.id,
            'content': report_content,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Analyse terminée'),
                'message': _('%d événements bloqués trouvés. Consultez les rapports.') % len(stuck_events),
                'type': 'warning',
                'sticky': True,
            }
        }

    def action_force_resync(self):
        """Force la resynchronisation immédiate des événements avec logging"""
        ICP = self.env['ir.config_parameter'].sudo()
        enable_logging = ICP.get_param('outlook_sync_analyzer.enable_logging', 'False') == 'True'

        ctx = {}
        if enable_logging:
            ctx['outlook_sync_enable_logging'] = True

        # Forcer la sync immédiate avec le contexte de logging
        for event in self.with_context(**ctx):
            if event.ms_organizer_event_id:
                # Événement existant → patch
                values = event._microsoft_values(event._get_microsoft_synced_fields())
                if values:
                    event._microsoft_patch(event._get_organizer(), event.ms_organizer_event_id, values)
            else:
                # Nouvel événement → insert
                event._microsoft_insert(event._microsoft_values(event._get_microsoft_synced_fields()))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Resynchronisation forcée'),
                'message': _('%d événements synchronisés avec Outlook') % len(self),
                'type': 'success',
            }
        }

    def action_view_sync_history(self):
        """Affiche l'historique de synchronisation pour cet événement"""
        self.ensure_one()
        return {
            'name': _('Historique de synchronisation'),
            'type': 'ir.actions.act_window',
            'res_model': 'microsoft.sync.log',
            'view_mode': 'list,form',
            'domain': [('event_id', '=', self.id)],
            'context': {'default_event_id': self.id},
        }
