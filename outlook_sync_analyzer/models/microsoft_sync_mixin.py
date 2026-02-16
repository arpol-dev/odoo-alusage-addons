# -*- coding: utf-8 -*-
"""
Extension du mixin microsoft.calendar.sync pour ajouter le traçage
"""
import logging
from odoo import models
from odoo.addons.microsoft_account.models.microsoft_service import TIMEOUT
from .microsoft_sync_log import MicrosoftSyncLogContext

_logger = logging.getLogger(__name__)


class MicrosoftSyncWithLogging(models.AbstractModel):
    _inherit = 'microsoft.calendar.sync'

    def _microsoft_insert(self, values, timeout=TIMEOUT):
        """Override pour logger les insertions"""
        if not self.env.context.get('outlook_sync_enable_logging'):
            return super()._microsoft_insert(values, timeout=timeout)

        sender_user = self._get_event_user_m()
        with MicrosoftSyncLogContext(
            self.env, sender_user, 'insert',
            event_id=self.id if hasattr(self, 'id') else False,
            event_name=self.name if hasattr(self, 'name') else '',
        ) as ctx:
            result = super()._microsoft_insert(values, timeout=timeout)
            ctx.update_stats(events_created=1)
            return result

    def _microsoft_patch(self, user_id, event_id, values, timeout=TIMEOUT):
        """Override pour logger les updates"""
        if not self.env.context.get('outlook_sync_enable_logging'):
            return super()._microsoft_patch(user_id, event_id, values, timeout=timeout)

        sender_user = self._get_event_user_m(user_id)
        with MicrosoftSyncLogContext(
            self.env, sender_user, 'patch',
            event_id=self.id if hasattr(self, 'id') else False,
            event_name=self.name if hasattr(self, 'name') else '',
            microsoft_event_id=event_id,
        ) as ctx:
            result = super()._microsoft_patch(user_id, event_id, values, timeout=timeout)
            ctx.update_stats(events_updated=1)
            return result

    def _microsoft_delete(self, user_id, event_id, timeout=TIMEOUT):
        """Override pour logger les suppressions"""
        if not self.env.context.get('outlook_sync_enable_logging'):
            return super()._microsoft_delete(user_id, event_id, timeout=timeout)

        sender_user = self._get_event_user_m(user_id)
        with MicrosoftSyncLogContext(
            self.env, sender_user, 'delete',
            event_id=self.id if hasattr(self, 'id') else False,
            event_name=self.name if hasattr(self, 'name') else '',
            microsoft_event_id=event_id,
        ) as ctx:
            result = super()._microsoft_delete(user_id, event_id, timeout=timeout)
            ctx.update_stats(events_deleted=1)
            return result

    def _sync_microsoft2odoo(self, microsoft_events):
        """Override pour logger la sync Microsoft → Odoo"""
        if not self.env.context.get('outlook_sync_enable_logging'):
            return super()._sync_microsoft2odoo(microsoft_events)

        with MicrosoftSyncLogContext(
            self.env, self.env.user, 'sync_m2o',
            events_count=len(microsoft_events),
        ) as ctx:
            synced_events, synced_recurrences = super()._sync_microsoft2odoo(microsoft_events)

            # Analyse des anomalies
            self._check_sync_anomalies(synced_events, ctx)

            ctx.update_stats(
                events_created=len(synced_events.filtered(lambda e: not e.microsoft_id)),
                events_updated=len(synced_events.filtered(lambda e: e.microsoft_id)),
            )

            return synced_events, synced_recurrences

    def _check_sync_anomalies(self, events, log_ctx):
        """Vérifie les anomalies dans les événements synchronisés"""
        ICP = self.env['ir.config_parameter'].sudo()

        # Vérifie les récurrences avec dates futures extrêmes
        future_limit_year = int(ICP.get_param('outlook_sync_analyzer.future_year_limit', 2030))
        extreme_future_events = events.filtered(
            lambda e: e.stop and e.stop.year > future_limit_year
        )
        if extreme_future_events:
            details = f"Événements avec dates > {future_limit_year}:\n"
            for event in extreme_future_events[:10]:  # Limite à 10 pour le rapport
                details += f"- {event.name}: {event.stop}\n"
            log_ctx.add_anomaly('future_recurrence', details)

        # Vérifie les événements anciens synchronisés
        old_event_limit_days = int(ICP.get_param('outlook_sync_analyzer.old_event_limit_days', 365))
        from datetime import datetime, timedelta
        old_limit = datetime.now() - timedelta(days=old_event_limit_days)
        old_events = events.filtered(
            lambda e: e.start and e.start < old_limit
        )
        if old_events:
            details = f"Événements de plus de {old_event_limit_days} jours synchronisés:\n"
            for event in old_events[:10]:
                details += f"- {event.name}: {event.start}\n"
            log_ctx.add_anomaly('old_event_sync', details)

        # Vérifie les événements sans email
        no_email_events = events.filtered(
            lambda e: any(not att.email for att in e.attendee_ids)
        )
        if no_email_events:
            details = f"Événements avec participants sans email:\n"
            for event in no_email_events[:10]:
                details += f"- {event.name}\n"
            log_ctx.add_anomaly('missing_email', details)
