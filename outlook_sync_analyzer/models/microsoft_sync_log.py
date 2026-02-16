# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from datetime import datetime

_logger = logging.getLogger(__name__)


class MicrosoftSyncLog(models.Model):
    _name = 'microsoft.sync.log'
    _description = 'Journal de synchronisation Microsoft Calendar'
    _order = 'create_date desc'
    _rec_name = 'operation'

    user_id = fields.Many2one('res.users', string='Utilisateur', required=True, index=True)
    operation = fields.Selection([
        ('sync_m2o', 'Microsoft → Odoo'),
        ('sync_o2m', 'Odoo → Microsoft'),
        ('insert', 'Insertion'),
        ('patch', 'Mise à jour'),
        ('delete', 'Suppression'),
        ('get_events', 'Récupération événements'),
        ('error', 'Erreur'),
    ], string='Opération', required=True, index=True)

    event_id = fields.Many2one('calendar.event', string='Événement', ondelete='set null')
    event_name = fields.Char('Nom événement')
    microsoft_event_id = fields.Char('ID Microsoft')

    status = fields.Selection([
        ('success', 'Succès'),
        ('error', 'Erreur'),
        ('timeout', 'Timeout'),
        ('partial', 'Partiel'),
    ], string='Statut', required=True, default='success', index=True)

    duration_ms = fields.Integer('Durée (ms)')
    events_count = fields.Integer('Nombre événements')
    events_created = fields.Integer('Créés')
    events_updated = fields.Integer('Mis à jour')
    events_deleted = fields.Integer('Supprimés')
    events_errors = fields.Integer('Erreurs')

    error_message = fields.Text('Message erreur')
    details = fields.Text('Détails')
    api_response_code = fields.Integer('Code réponse API')

    sync_token = fields.Char('Token de sync')
    full_sync = fields.Boolean('Sync complète')

    # Statistiques sur les événements need_sync_m
    need_sync_count_before = fields.Integer('Need sync avant')
    need_sync_count_after = fields.Integer('Need sync après')

    # Détection anomalies
    has_anomaly = fields.Boolean('Anomalie détectée', index=True)
    anomaly_type = fields.Selection([
        ('future_recurrence', 'Récurrence future extrême'),
        ('old_event_sync', 'Événement ancien synchronisé'),
        ('stuck_need_sync', 'Need_sync_m bloqué'),
        ('duplicate', 'Doublon'),
        ('missing_email', 'Email manquant'),
    ], string='Type anomalie')
    anomaly_details = fields.Text('Détails anomalie')

    def write_markdown_report(self):
        """Génère un rapport markdown pour ce log"""
        self.ensure_one()
        report_lines = [
            f"# Rapport de synchronisation Outlook",
            f"",
            f"**Date:** {self.create_date}",
            f"**Utilisateur:** {self.user_id.name} ({self.user_id.login})",
            f"**Opération:** {dict(self._fields['operation'].selection).get(self.operation)}",
            f"**Statut:** {dict(self._fields['status'].selection).get(self.status)}",
            f"",
            f"## Statistiques",
            f"",
            f"- Durée: {self.duration_ms}ms",
            f"- Événements traités: {self.events_count}",
            f"- Créés: {self.events_created}",
            f"- Mis à jour: {self.events_updated}",
            f"- Supprimés: {self.events_deleted}",
            f"- Erreurs: {self.events_errors}",
            f"",
            f"## Need Sync Status",
            f"",
            f"- Avant: {self.need_sync_count_before}",
            f"- Après: {self.need_sync_count_after}",
            f"- Delta: {self.need_sync_count_after - self.need_sync_count_before:+d}",
        ]

        if self.has_anomaly:
            report_lines.extend([
                f"",
                f"## ⚠️ Anomalie détectée",
                f"",
                f"**Type:** {dict(self._fields['anomaly_type'].selection).get(self.anomaly_type)}",
                f"",
                f"**Détails:**",
                f"```",
                self.anomaly_details or 'Aucun détail',
                f"```",
            ])

        if self.error_message:
            report_lines.extend([
                f"",
                f"## ❌ Erreur",
                f"",
                f"```",
                self.error_message,
                f"```",
            ])

        if self.details:
            report_lines.extend([
                f"",
                f"## Détails techniques",
                f"",
                f"```",
                self.details,
                f"```",
            ])

        return '\n'.join(report_lines)


class MicrosoftSyncLogContext:
    """Context manager pour logger automatiquement les opérations de sync"""

    def __init__(self, env, user_id, operation, **kwargs):
        self.env = env
        self.user_id = user_id
        self.operation = operation
        self.kwargs = kwargs
        self.start_time = None
        self.log = None

    def __enter__(self):
        self.start_time = datetime.now()

        # Compte les need_sync_m avant
        need_sync_count = self.env['calendar.event'].search_count([
            ('partner_ids.user_ids', 'in', self.user_id.id),
            ('need_sync_m', '=', True),
        ])

        self.log = self.env['microsoft.sync.log'].create({
            'user_id': self.user_id.id,
            'operation': self.operation,
            'status': 'success',
            'need_sync_count_before': need_sync_count,
            **self.kwargs
        })
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((datetime.now() - self.start_time).total_seconds() * 1000)

        # Compte les need_sync_m après
        need_sync_count = self.env['calendar.event'].search_count([
            ('partner_ids.user_ids', 'in', self.user_id.id),
            ('need_sync_m', '=', True),
        ])

        vals = {
            'duration_ms': duration_ms,
            'need_sync_count_after': need_sync_count,
        }

        if exc_type:
            vals.update({
                'status': 'timeout' if 'timeout' in str(exc_val).lower() else 'error',
                'error_message': str(exc_val),
            })

        self.log.write(vals)

        # Génère le rapport markdown
        if self.env.context.get('outlook_sync_generate_reports'):
            report_content = self.log.write_markdown_report()
            self.env['microsoft.sync.report'].create({
                'log_id': self.log.id,
                'user_id': self.user_id.id,
                'content': report_content,
            })

        return False  # Ne pas supprimer l'exception

    def update_stats(self, **stats):
        """Met à jour les statistiques du log"""
        if self.log:
            self.log.write(stats)

    def add_anomaly(self, anomaly_type, details):
        """Signale une anomalie"""
        if self.log:
            self.log.write({
                'has_anomaly': True,
                'anomaly_type': anomaly_type,
                'anomaly_details': details,
            })
