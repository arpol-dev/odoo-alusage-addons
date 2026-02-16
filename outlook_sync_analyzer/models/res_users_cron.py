# -*- coding: utf-8 -*-
"""
Override du cron de synchronisation pour logger automatiquement
"""
import logging
from datetime import datetime
from odoo import api, models, fields, _
from odoo.loglevels import exception_to_unicode

_logger = logging.getLogger(__name__)


class ResUsersCronLogging(models.Model):
    _inherit = 'res.users'

    @api.model
    def _sync_all_microsoft_calendar(self):
        """
        Override du cron de synchronisation pour générer automatiquement
        un rapport markdown à chaque exécution
        """
        # Vérifier si le logging est activé
        ICP = self.env['ir.config_parameter'].sudo()
        enable_logging = ICP.get_param('outlook_sync_analyzer.enable_logging', 'False')
        generate_reports = ICP.get_param('outlook_sync_analyzer.generate_reports', 'False')

        if enable_logging != 'True' and generate_reports != 'True':
            # Si logging désactivé, appeler la méthode parente normalement
            return super()._sync_all_microsoft_calendar()

        # Début de la synchronisation
        cron_start = datetime.now()
        _logger.info("=" * 80)
        _logger.info("OUTLOOK SYNC CRON - Début de la synchronisation automatique")
        _logger.info("=" * 80)

        users = self.env['res.users'].search([
            ('microsoft_calendar_rtoken', '!=', False),
            ('microsoft_synchronization_stopped', '=', False)
        ])

        _logger.info(f"Utilisateurs à synchroniser: {len(users)}")

        # Statistiques globales avant
        total_events_before = self.env['calendar.event'].search_count([])
        need_sync_before = self.env['calendar.event'].search_count([('need_sync_m', '=', True)])

        # Statistiques par utilisateur
        user_stats = []

        for user in users:
            user_start = datetime.now()
            _logger.info(f"\n{'─' * 60}")
            _logger.info(f"🔄 Synchronisation de {user.name} ({user.login})")

            # Statistiques utilisateur AVANT
            user_events_before = self.env['calendar.event'].search_count([
                ('partner_ids.user_ids', 'in', user.id),
            ])
            user_need_sync_before = self.env['calendar.event'].search_count([
                ('partner_ids.user_ids', 'in', user.id),
                ('need_sync_m', '=', True),
            ])

            try:
                # Exécuter la synchronisation pour cet utilisateur avec le contexte de logging
                ctx = {}
                if enable_logging == 'True':
                    ctx['outlook_sync_enable_logging'] = True

                result = user.with_user(user).with_context(**ctx).sudo()._sync_microsoft_calendar()
                user_status = 'success'
                user_error = None

                # Calculer la durée
                user_duration = (datetime.now() - user_start).total_seconds() * 1000

                # Statistiques utilisateur APRÈS
                user_events_after = self.env['calendar.event'].search_count([
                    ('partner_ids.user_ids', 'in', user.id),
                ])
                user_need_sync_after = self.env['calendar.event'].search_count([
                    ('partner_ids.user_ids', 'in', user.id),
                    ('need_sync_m', '=', True),
                ])

                events_created = max(0, user_events_after - user_events_before)
                events_synced = max(0, user_need_sync_before - user_need_sync_after)

                _logger.info(f"  ✓ Terminé en {user_duration:.0f}ms")
                _logger.info(f"  📊 Événements: {user_events_after} total ({events_created:+d})")
                _logger.info(f"  📋 Need sync: {user_need_sync_after} ({user_need_sync_after - user_need_sync_before:+d})")
                _logger.info(f"  ✅ Synchronisés: {events_synced}")

                user_stats.append({
                    'user': user,
                    'status': user_status,
                    'duration_ms': user_duration,
                    'events_total_before': user_events_before,
                    'events_total_after': user_events_after,
                    'events_created': events_created,
                    'need_sync_before': user_need_sync_before,
                    'need_sync_after': user_need_sync_after,
                    'events_synced': events_synced,
                    'error': None,
                })

                self.env.cr.commit()

            except Exception as e:
                error_msg = exception_to_unicode(e)
                user_duration = (datetime.now() - user_start).total_seconds() * 1000

                _logger.exception(f"  ❌ Erreur après {user_duration:.0f}ms: {error_msg}")

                user_stats.append({
                    'user': user,
                    'status': 'error',
                    'duration_ms': user_duration,
                    'events_total_before': user_events_before,
                    'events_total_after': user_events_before,  # Pas de changement
                    'events_created': 0,
                    'need_sync_before': user_need_sync_before,
                    'need_sync_after': user_need_sync_before,  # Pas de changement
                    'events_synced': 0,
                    'error': error_msg,
                })

                self.env.cr.rollback()

        # Statistiques globales après
        total_events_after = self.env['calendar.event'].search_count([])
        need_sync_after = self.env['calendar.event'].search_count([('need_sync_m', '=', True)])

        # Durée totale
        cron_duration = (datetime.now() - cron_start).total_seconds()

        _logger.info(f"\n{'═' * 80}")
        _logger.info(f"OUTLOOK SYNC CRON - Synchronisation terminée")
        _logger.info(f"  Durée totale: {cron_duration:.1f}s")
        _logger.info(f"  Événements totaux: {total_events_after} ({total_events_after - total_events_before:+d})")
        _logger.info(f"  Need sync global: {need_sync_after} ({need_sync_after - need_sync_before:+d})")
        _logger.info(f"  Utilisateurs en succès: {sum(1 for s in user_stats if s['status'] == 'success')}/{len(users)}")
        if any(s['status'] == 'error' for s in user_stats):
            _logger.warning(f"  ⚠️  Utilisateurs en erreur: {sum(1 for s in user_stats if s['status'] == 'error')}")
        _logger.info(f"{'═' * 80}")

        # Générer le rapport markdown si activé
        if generate_reports == 'True':
            self._generate_cron_report(
                cron_start=cron_start,
                cron_duration=cron_duration,
                user_stats=user_stats,
                total_events_before=total_events_before,
                total_events_after=total_events_after,
                need_sync_before=need_sync_before,
                need_sync_after=need_sync_after,
            )

    @api.model
    def _generate_cron_report(self, cron_start, cron_duration, user_stats, total_events_before,
                              total_events_after, need_sync_before, need_sync_after):
        """Génère un rapport markdown pour l'exécution du cron"""

        # Calculer les statistiques agrégées
        total_users = len(user_stats)
        success_users = sum(1 for s in user_stats if s['status'] == 'success')
        error_users = sum(1 for s in user_stats if s['status'] == 'error')
        total_events_created = sum(s['events_created'] for s in user_stats)
        total_events_synced = sum(s['events_synced'] for s in user_stats)
        total_duration_sync = sum(s['duration_ms'] for s in user_stats) / 1000  # en secondes

        # Construire le rapport markdown
        report_lines = [
            f"# Rapport de synchronisation Outlook - Tâche planifiée",
            f"",
            f"**Date d'exécution:** {cron_start.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Durée totale:** {cron_duration:.1f}s",
            f"**Durée de synchronisation (utilisateurs):** {total_duration_sync:.1f}s",
            f"",
            f"## Synthèse",
            f"",
            f"| Métrique | Avant | Après | Delta |",
            f"|----------|-------|-------|-------|",
            f"| **Événements totaux** | {total_events_before} | {total_events_after} | {total_events_after - total_events_before:+d} |",
            f"| **Need sync global** | {need_sync_before} | {need_sync_after} | {need_sync_after - need_sync_before:+d} |",
            f"| **Événements créés** | - | {total_events_created} | +{total_events_created} |",
            f"| **Événements synchronisés** | - | {total_events_synced} | +{total_events_synced} |",
            f"",
            f"## Utilisateurs",
            f"",
            f"- Total utilisateurs: {total_users}",
            f"- ✅ Succès: {success_users}",
        ]

        if error_users > 0:
            report_lines.append(f"- ❌ Erreurs: {error_users}")

        report_lines.extend([
            f"",
            f"## Détails par utilisateur",
            f"",
            f"| Utilisateur | Statut | Durée (ms) | Total | Créés | Need Sync | Synchronisés |",
            f"|-------------|--------|------------|-------|-------|-----------|--------------|",
        ])

        # Trier par durée décroissante
        user_stats_sorted = sorted(user_stats, key=lambda x: -x['duration_ms'])

        for stat in user_stats_sorted:
            status_icon = '✓' if stat['status'] == 'success' else '❌'
            delta_need_sync = stat['need_sync_after'] - stat['need_sync_before']

            report_lines.append(
                f"| {stat['user'].name} | {status_icon} | {stat['duration_ms']:.0f} | "
                f"{stat['events_total_after']} | +{stat['events_created']} | "
                f"{stat['need_sync_after']} ({delta_need_sync:+d}) | "
                f"{stat['events_synced']} |"
            )

        # Ajouter les erreurs si présentes
        error_stats = [s for s in user_stats if s['status'] == 'error']
        if error_stats:
            report_lines.extend([
                f"",
                f"## ❌ Erreurs rencontrées",
                f"",
            ])
            for stat in error_stats:
                report_lines.extend([
                    f"### {stat['user'].name} ({stat['user'].login})",
                    f"",
                    f"```",
                    stat['error'] or 'Erreur inconnue',
                    f"```",
                    f"",
                ])

        # Détection d'anomalies
        stuck_events = self.env['calendar.event'].search_count([
            ('need_sync_m', '=', True),
            ('write_date', '<', fields.Datetime.subtract(fields.Datetime.now(), days=7)),
        ])

        extreme_future = self.env['calendar.event'].search_count([
            ('stop', '>', f'{datetime.now().year + 10}-01-01'),
        ])

        if stuck_events > 0 or extreme_future > 0:
            report_lines.extend([
                f"",
                f"## ⚠️ Anomalies détectées",
                f"",
            ])

            if stuck_events > 0:
                report_lines.append(f"- **Événements bloqués (>7 jours):** {stuck_events}")

            if extreme_future > 0:
                report_lines.append(f"- **Événements futur extrême:** {extreme_future}")

        # Recommandations
        report_lines.extend([
            f"",
            f"## 📋 Recommandations",
            f"",
        ])

        if error_users > 0:
            report_lines.append(f"- Consulter les erreurs ci-dessus et corriger les problèmes (token, connexion, etc.)")

        if stuck_events > 10:
            report_lines.append(f"- **{stuck_events} événements bloqués** : Utiliser l'analyse détaillée pour diagnostiquer")

        if extreme_future > 0:
            report_lines.append(f"- **{extreme_future} événements avec dates extrêmes** : Nettoyer les récurrences anormales")

        if need_sync_after > 100:
            report_lines.append(f"- **{need_sync_after} événements à synchroniser** : Vérifier si la synchronisation se passe correctement")

        if not error_users and stuck_events < 10 and extreme_future == 0 and need_sync_after < 50:
            report_lines.append(f"- ✅ **Aucune action requise** : La synchronisation fonctionne correctement")

        # Performance
        report_lines.extend([
            f"",
            f"## ⏱️ Performance",
            f"",
            f"- Temps total: {cron_duration:.1f}s",
            f"- Temps de synchronisation: {total_duration_sync:.1f}s",
            f"- Temps moyen par utilisateur: {(total_duration_sync / total_users):.1f}s",
        ])

        if total_users > 0:
            slowest = max(user_stats, key=lambda x: x['duration_ms'])
            fastest = min(user_stats, key=lambda x: x['duration_ms'])

            report_lines.extend([
                f"- Plus rapide: {fastest['user'].name} ({fastest['duration_ms']:.0f}ms)",
                f"- Plus lent: {slowest['user'].name} ({slowest['duration_ms']:.0f}ms)",
            ])

        report_content = '\n'.join(report_lines)

        # Créer le rapport
        try:
            log = self.env['microsoft.sync.log'].create({
                'user_id': self.env.uid,
                'operation': 'sync_m2o',
                'status': 'success' if error_users == 0 else 'partial',
                'duration_ms': int(cron_duration * 1000),
                'events_count': total_events_after,
                'events_created': total_events_created,
                'events_errors': error_users,
                'need_sync_count_before': need_sync_before,
                'need_sync_count_after': need_sync_after,
                'has_anomaly': stuck_events > 0 or extreme_future > 0,
                'full_sync': False,
            })

            report = self.env['microsoft.sync.report'].create({
                'log_id': log.id,
                'user_id': self.env.uid,
                'content': report_content,
            })

            # Sauvegarder automatiquement
            report.action_save_to_file()

            _logger.info(f"📄 Rapport de synchronisation généré: {report.name}")

        except Exception as e:
            _logger.error(f"Erreur lors de la génération du rapport: {e}")
