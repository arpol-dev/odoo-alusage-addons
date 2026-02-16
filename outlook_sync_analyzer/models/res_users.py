# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ResUsers(models.Model):
    _inherit = 'res.users'

    # Statistiques de synchronisation
    outlook_sync_stats_last_sync = fields.Datetime('Dernière sync Outlook')
    outlook_sync_stats_events_synced = fields.Integer('Événements synchronisés', compute='_compute_outlook_stats')
    outlook_sync_stats_events_need_sync = fields.Integer('Événements à synchroniser', compute='_compute_outlook_stats')
    outlook_sync_stats_events_stuck = fields.Integer('Événements bloqués', compute='_compute_outlook_stats')
    outlook_sync_stats_last_error = fields.Char('Dernière erreur')

    @api.depends_context('uid')
    def _compute_outlook_stats(self):
        for user in self:
            events = self.env['calendar.event'].search([
                ('partner_ids.user_ids', 'in', user.id),
            ])

            synced = events.filtered(lambda e: e.microsoft_id)
            need_sync = events.filtered(lambda e: e.need_sync_m)
            stuck = events.filtered(lambda e: e.sync_analysis_state == 'stuck')

            user.outlook_sync_stats_events_synced = len(synced)
            user.outlook_sync_stats_events_need_sync = len(need_sync)
            user.outlook_sync_stats_events_stuck = len(stuck)

    def action_view_outlook_sync_report(self):
        """Affiche un rapport de synchronisation pour cet utilisateur"""
        self.ensure_one()

        events = self.env['calendar.event'].search([
            ('partner_ids.user_ids', 'in', self.id),
        ])

        report_lines = [
            f"# Rapport de synchronisation Outlook",
            f"",
            f"**Utilisateur:** {self.name} ({self.login})",
            f"**Date:** {fields.Datetime.now()}",
            f"",
            f"## Statistiques globales",
            f"",
            f"- Total événements: {len(events)}",
            f"- Synchronisés avec Outlook: {len(events.filtered(lambda e: e.microsoft_id))}",
            f"- À synchroniser (need_sync_m): {len(events.filtered(lambda e: e.need_sync_m))}",
            f"- Bloqués (>7 jours): {len(events.filtered(lambda e: e.sync_analysis_state == 'stuck'))}",
            f"",
            f"## Répartition par état",
            f"",
        ]

        # Comptage par état d'analyse
        states_count = {}
        for event in events:
            state = event.sync_analysis_state or 'unknown'
            states_count[state] = states_count.get(state, 0) + 1

        for state, count in sorted(states_count.items(), key=lambda x: -x[1]):
            state_label = dict(
                self.env['calendar.event']._fields['sync_analysis_state'].selection
            ).get(state, state)
            report_lines.append(f"- {state_label}: {count}")

        report_lines.extend([
            f"",
            f"## Événements need_sync_m",
            f"",
        ])

        need_sync_events = events.filtered(lambda e: e.need_sync_m)
        if need_sync_events:
            report_lines.append(f"| Événement | Date début | Jours bloqué | Microsoft ID |")
            report_lines.append(f"|-----------|------------|--------------|--------------|")
            for event in need_sync_events[:50]:
                days_stuck = event.sync_stuck_days
                report_lines.append(
                    f"| {event.name} | {event.start} | {days_stuck} | {event.microsoft_id or 'N/A'} |"
                )
            if len(need_sync_events) > 50:
                report_lines.append(f"| ... et {len(need_sync_events) - 50} autres | | | |")
        else:
            report_lines.append("Aucun événement en attente de synchronisation.")

        # Événements avec dates futures extrêmes
        extreme_future = events.filtered(lambda e: e.sync_analysis_state == 'extreme_future')
        if extreme_future:
            report_lines.extend([
                f"",
                f"## ⚠️ Événements avec dates futures extrêmes",
                f"",
                f"| Événement | Date début | Date fin |",
                f"|-----------|------------|----------|",
            ])
            for event in extreme_future[:20]:
                report_lines.append(f"| {event.name} | {event.start} | {event.stop} |")
            if len(extreme_future) > 20:
                report_lines.append(f"| ... et {len(extreme_future) - 20} autres | | |")

        report_content = '\n'.join(report_lines)

        # Crée le rapport
        report = self.env['microsoft.sync.report'].create({
            'log_id': self.env['microsoft.sync.log'].create({
                'user_id': self.id,
                'operation': 'sync_o2m',
                'status': 'success',
                'events_count': len(events),
            }).id,
            'user_id': self.id,
            'content': report_content,
        })

        # Affiche le rapport
        return {
            'name': _('Rapport de synchronisation'),
            'type': 'ir.actions.act_window',
            'res_model': 'microsoft.sync.report',
            'res_id': report.id,
            'view_mode': 'form',
            'target': 'new',
        }
