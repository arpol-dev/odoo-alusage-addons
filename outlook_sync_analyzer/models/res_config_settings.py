# -*- coding: utf-8 -*-
from odoo import fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Activation du logging
    outlook_sync_enable_logging = fields.Boolean(
        string='Activer le logging détaillé',
        config_parameter='outlook_sync_analyzer.enable_logging',
        help='Active le traçage détaillé de toutes les opérations de synchronisation Outlook'
    )

    outlook_sync_generate_reports = fields.Boolean(
        string='Générer des rapports markdown',
        config_parameter='outlook_sync_analyzer.generate_reports',
        help='Génère automatiquement un rapport markdown à chaque synchronisation'
    )

    # Limites de synchronisation
    outlook_sync_future_year_limit = fields.Integer(
        string='Limite année future',
        config_parameter='outlook_sync_analyzer.future_year_limit',
        default=2030,
        help='Année maximale pour les événements récurrents (détection anomalies)'
    )

    outlook_sync_old_event_limit_days = fields.Integer(
        string='Limite événements anciens (jours)',
        config_parameter='outlook_sync_analyzer.old_event_limit_days',
        default=365,
        help='Ne pas synchroniser les événements de plus de X jours'
    )

    # Paramètres Microsoft Calendar existants
    microsoft_calendar_sync_range_days = fields.Integer(
        string='Plage de synchronisation (jours)',
        config_parameter='microsoft_calendar.sync.range_days',
        default=365,
        help='Nombre de jours dans le passé et le futur à synchroniser (API Microsoft)'
    )

    microsoft_calendar_sync_lower_bound_range = fields.Integer(
        string='Borne inférieure sync (jours)',
        config_parameter='microsoft_calendar.sync.lower_bound_range',
        help='Limite les mises à jour d\'événements anciens dans Odoo pour éviter le spam sur Microsoft'
    )

    microsoft_calendar_first_sync_date = fields.Datetime(
        string='Date première synchronisation',
        config_parameter='microsoft_calendar.sync.first_synchronization_date',
        help='Synchronise uniquement les événements créés après cette date'
    )

    def action_analyze_all_users(self):
        """Génère un rapport global pour tous les utilisateurs"""
        users = self.env['res.users'].search([
            ('microsoft_calendar_rtoken', '!=', False),
        ])

        report_lines = [
            f"# Rapport global de synchronisation Outlook",
            f"",
            f"**Date:** {fields.Datetime.now()}",
            f"**Nombre d'utilisateurs:** {len(users)}",
            f"",
            f"## Synthèse par utilisateur",
            f"",
            f"| Utilisateur | Total | Synchronisés | Need Sync | Bloqués |",
            f"|-------------|-------|--------------|-----------|---------|",
        ]

        total_events = 0
        total_synced = 0
        total_need_sync = 0
        total_stuck = 0

        for user in users:
            events = self.env['calendar.event'].search([
                ('partner_ids.user_ids', 'in', user.id),
            ])
            synced = len(events.filtered(lambda e: e.microsoft_id))
            need_sync = len(events.filtered(lambda e: e.need_sync_m))
            stuck = len(events.filtered(lambda e: e.sync_analysis_state == 'stuck'))

            report_lines.append(
                f"| {user.name} | {len(events)} | {synced} | {need_sync} | {stuck} |"
            )

            total_events += len(events)
            total_synced += synced
            total_need_sync += need_sync
            total_stuck += stuck

        report_lines.extend([
            f"| **TOTAL** | **{total_events}** | **{total_synced}** | **{total_need_sync}** | **{total_stuck}** |",
            f"",
            f"## Anomalies détectées",
            f"",
        ])

        # Cherche les anomalies récentes
        recent_anomalies = self.env['microsoft.sync.log'].search([
            ('has_anomaly', '=', True),
            ('create_date', '>=', fields.Datetime.subtract(fields.Datetime.now(), days=7)),
        ], order='create_date desc', limit=50)

        if recent_anomalies:
            report_lines.append(f"| Date | Utilisateur | Type | Détails |")
            report_lines.append(f"|------|-------------|------|---------|")
            for anomaly in recent_anomalies:
                anomaly_type = dict(anomaly._fields['anomaly_type'].selection).get(anomaly.anomaly_type, '')
                details = (anomaly.anomaly_details or '')[:50]
                report_lines.append(
                    f"| {anomaly.create_date} | {anomaly.user_id.name} | {anomaly_type} | {details}... |"
                )
        else:
            report_lines.append("Aucune anomalie détectée dans les 7 derniers jours.")

        report_content = '\n'.join(report_lines)

        # Crée le rapport
        report = self.env['microsoft.sync.report'].create({
            'log_id': self.env['microsoft.sync.log'].create({
                'user_id': self.env.user.id,
                'operation': 'sync_m2o',
                'status': 'success',
                'events_count': total_events,
            }).id,
            'user_id': self.env.user.id,
            'content': report_content,
        })

        return {
            'name': _('Rapport global'),
            'type': 'ir.actions.act_window',
            'res_model': 'microsoft.sync.report',
            'res_id': report.id,
            'view_mode': 'form',
            'target': 'new',
        }
