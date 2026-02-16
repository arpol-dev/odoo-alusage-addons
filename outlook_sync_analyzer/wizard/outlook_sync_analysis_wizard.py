# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import datetime, timedelta


class OutlookSyncAnalysisWizard(models.TransientModel):
    _name = 'outlook.sync.analysis.wizard'
    _description = 'Assistant d\'analyse de synchronisation Outlook'

    analysis_type = fields.Selection([
        ('global', 'Analyse globale'),
        ('user', 'Par utilisateur'),
        ('stuck_events', 'Événements bloqués'),
        ('extreme_future', 'Récurrences anormales'),
        ('user_comparison', 'Comparaison utilisateurs'),
    ], string='Type d\'analyse', required=True, default='global')

    user_ids = fields.Many2many('res.users', string='Utilisateurs', help='Laisser vide pour tous les utilisateurs avec sync Outlook')
    days_stuck_threshold = fields.Integer('Seuil jours bloqués', default=7, help='Événements bloqués depuis plus de X jours')
    future_year_threshold = fields.Integer('Seuil année future', default=2030, help='Détecter les événements au-delà de cette année')

    # Résultats de l'analyse
    analysis_date = fields.Datetime('Date analyse', readonly=True)
    total_events = fields.Integer('Total événements', readonly=True)
    synced_events = fields.Integer('Événements synchronisés', readonly=True)
    need_sync_events = fields.Integer('À synchroniser', readonly=True)
    stuck_events_count = fields.Integer('Événements bloqués', readonly=True)
    extreme_future_count = fields.Integer('Futur extrême', readonly=True)

    result_html = fields.Html('Résultats', readonly=True)
    result_markdown = fields.Text('Résultats (markdown)', readonly=True)

    report_id = fields.Many2one('microsoft.sync.report', string='Rapport généré', readonly=True)

    def action_run_analysis(self):
        """Exécute l'analyse selon le type sélectionné"""
        self.ensure_one()

        self.analysis_date = fields.Datetime.now()

        if self.analysis_type == 'global':
            result = self._analyze_global()
        elif self.analysis_type == 'user':
            result = self._analyze_by_user()
        elif self.analysis_type == 'stuck_events':
            result = self._analyze_stuck_events()
        elif self.analysis_type == 'extreme_future':
            result = self._analyze_extreme_future()
        elif self.analysis_type == 'user_comparison':
            result = self._analyze_user_comparison()

        # Mettre à jour les statistiques
        self.write({
            'total_events': result.get('total_events', 0),
            'synced_events': result.get('synced_events', 0),
            'need_sync_events': result.get('need_sync_events', 0),
            'stuck_events_count': result.get('stuck_events_count', 0),
            'extreme_future_count': result.get('extreme_future_count', 0),
            'result_html': result.get('html', ''),
            'result_markdown': result.get('markdown', ''),
        })

        # Créer un rapport si nécessaire
        if result.get('markdown'):
            report = self.env['microsoft.sync.report'].create({
                'log_id': self.env['microsoft.sync.log'].create({
                    'user_id': self.env.user.id,
                    'operation': 'sync_m2o',
                    'status': 'success',
                    'events_count': result.get('total_events', 0),
                }).id,
                'user_id': self.env.user.id,
                'content': result.get('markdown', ''),
                'content_html': result.get('html', ''),
            })
            self.report_id = report.id

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'outlook.sync.analysis.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'form_view_initial_mode': 'readonly'},
        }

    def _get_base_stats(self):
        """Récupère les statistiques de base"""
        events = self.env['calendar.event'].search([])
        return {
            'total_events': len(events),
            'synced_events': len(events.filtered(lambda e: e.microsoft_id)),
            'need_sync_events': len(events.filtered(lambda e: e.need_sync_m)),
            'stuck_events_count': len(events.filtered(
                lambda e: e.need_sync_m and e.write_date and
                         (fields.Datetime.now() - e.write_date).days > self.days_stuck_threshold
            )),
            'extreme_future_count': len(events.filtered(
                lambda e: e.stop and e.stop.year > self.future_year_threshold
            )),
        }

    def _analyze_global(self):
        """Analyse globale de la synchronisation"""
        stats = self._get_base_stats()

        users = self.env['res.users'].search([
            ('microsoft_calendar_rtoken', '!=', False),
        ])

        html = f"""
        <div class="o_outlook_sync_analysis">
            <h2>📊 Analyse globale de la synchronisation Outlook</h2>
            <p><strong>Date:</strong> {self.analysis_date}</p>

            <h3>Statistiques générales</h3>
            <table class="table table-striped">
                <tr><td><strong>Total événements</strong></td><td class="text-right">{stats['total_events']}</td></tr>
                <tr><td><strong>Synchronisés avec Outlook</strong></td><td class="text-right">{stats['synced_events']}</td></tr>
                <tr><td><strong>À synchroniser (need_sync_m)</strong></td><td class="text-right {'text-warning' if stats['need_sync_events'] > 50 else ''}">{stats['need_sync_events']}</td></tr>
                <tr><td><strong>Bloqués (&gt;{self.days_stuck_threshold} jours)</strong></td><td class="text-right {'text-danger' if stats['stuck_events_count'] > 10 else ''}">{stats['stuck_events_count']}</td></tr>
                <tr><td><strong>Futur extrême (&gt;{self.future_year_threshold})</strong></td><td class="text-right {'text-danger' if stats['extreme_future_count'] > 0 else ''}">{stats['extreme_future_count']}</td></tr>
            </table>

            <h3>Utilisateurs</h3>
            <p>Nombre d'utilisateurs avec synchronisation Outlook configurée: <strong>{len(users)}</strong></p>
        """

        if stats['stuck_events_count'] > 10:
            html += f"""
            <div class="alert alert-danger">
                <strong>⚠️ ATTENTION:</strong> {stats['stuck_events_count']} événements sont bloqués depuis plus de {self.days_stuck_threshold} jours !
                <br/>Utilisez l'analyse "Événements bloqués" pour plus de détails.
            </div>
            """

        if stats['extreme_future_count'] > 0:
            html += f"""
            <div class="alert alert-warning">
                <strong>⚠️ ATTENTION:</strong> {stats['extreme_future_count']} événements ont des dates futures extrêmes !
                <br/>Utilisez l'analyse "Récurrences anormales" pour plus de détails.
            </div>
            """

        html += """
            <h3>Actions recommandées</h3>
            <ul>
        """

        if stats['stuck_events_count'] > 10:
            html += """
                <li>Consulter l'analyse des événements bloqués</li>
                <li>Vérifier les logs de synchronisation</li>
                <li>Forcer la resynchronisation si nécessaire</li>
            """

        if stats['extreme_future_count'] > 0:
            html += """
                <li>Consulter l'analyse des récurrences anormales</li>
                <li>Nettoyer les événements avec dates extrêmes</li>
            """

        html += """
            </ul>
        </div>
        """

        markdown = f"""
# Analyse globale de synchronisation Outlook

**Date:** {self.analysis_date}

## Statistiques générales

- Total événements: {stats['total_events']}
- Synchronisés avec Outlook: {stats['synced_events']}
- À synchroniser (need_sync_m): {stats['need_sync_events']}
- Bloqués (>{self.days_stuck_threshold} jours): {stats['stuck_events_count']}
- Futur extrême (>{self.future_year_threshold}): {stats['extreme_future_count']}

## Utilisateurs

Nombre d'utilisateurs avec synchronisation Outlook: {len(users)}
"""

        if stats['stuck_events_count'] > 10:
            markdown += f"\n⚠️ **ATTENTION:** {stats['stuck_events_count']} événements bloqués !\n"

        if stats['extreme_future_count'] > 0:
            markdown += f"\n⚠️ **ATTENTION:** {stats['extreme_future_count']} événements avec dates extrêmes !\n"

        return {
            'html': html,
            'markdown': markdown,
            **stats
        }

    def _analyze_by_user(self):
        """Analyse détaillée par utilisateur"""
        stats = self._get_base_stats()

        users = self.user_ids if self.user_ids else self.env['res.users'].search([
            ('microsoft_calendar_rtoken', '!=', False),
        ])

        html = f"""
        <div class="o_outlook_sync_analysis">
            <h2>👥 Analyse par utilisateur</h2>
            <p><strong>Date:</strong> {self.analysis_date}</p>
            <p><strong>Utilisateurs analysés:</strong> {len(users)}</p>

            <table class="table table-striped table-sm">
                <thead>
                    <tr>
                        <th>Utilisateur</th>
                        <th class="text-right">Total</th>
                        <th class="text-right">Synced</th>
                        <th class="text-right">Need Sync</th>
                        <th class="text-right">Bloqués</th>
                        <th>Dernière sync</th>
                    </tr>
                </thead>
                <tbody>
        """

        markdown_lines = [
            f"# Analyse par utilisateur",
            f"",
            f"**Date:** {self.analysis_date}",
            f"**Utilisateurs analysés:** {len(users)}",
            f"",
            f"| Utilisateur | Total | Synced | Need Sync | Bloqués | Dernière sync |",
            f"|-------------|-------|--------|-----------|---------|---------------|",
        ]

        user_stats = []
        for user in users:
            events = self.env['calendar.event'].search([
                ('partner_ids.user_ids', 'in', user.id),
            ])

            synced = len(events.filtered(lambda e: e.microsoft_id))
            need_sync = len(events.filtered(lambda e: e.need_sync_m))
            stuck = len(events.filtered(
                lambda e: e.need_sync_m and e.write_date and
                         (fields.Datetime.now() - e.write_date).days > self.days_stuck_threshold
            ))
            last_sync = user.microsoft_last_sync_date.strftime('%Y-%m-%d %H:%M') if user.microsoft_last_sync_date else 'N/A'

            user_stats.append({
                'user': user,
                'total': len(events),
                'synced': synced,
                'need_sync': need_sync,
                'stuck': stuck,
                'last_sync': last_sync,
            })

        # Trier par nombre d'événements bloqués (décroissant)
        user_stats.sort(key=lambda x: -x['stuck'])

        for stat in user_stats:
            row_class = 'table-danger' if stat['stuck'] > 10 else ''
            html += f"""
                    <tr class="{row_class}">
                        <td>{stat['user'].name}</td>
                        <td class="text-right">{stat['total']}</td>
                        <td class="text-right">{stat['synced']}</td>
                        <td class="text-right">{stat['need_sync']}</td>
                        <td class="text-right {'text-danger' if stat['stuck'] > 0 else ''}">{stat['stuck']}</td>
                        <td>{stat['last_sync']}</td>
                    </tr>
            """

            markdown_lines.append(
                f"| {stat['user'].name} | {stat['total']} | {stat['synced']} | "
                f"{stat['need_sync']} | {stat['stuck']} | {stat['last_sync']} |"
            )

        html += """
                </tbody>
            </table>
        </div>
        """

        return {
            'html': html,
            'markdown': '\n'.join(markdown_lines),
            **stats
        }

    def _analyze_stuck_events(self):
        """Analyse des événements bloqués"""
        stats = self._get_base_stats()

        events = self.env['calendar.event'].search([
            ('need_sync_m', '=', True),
            ('write_date', '<', fields.Datetime.subtract(fields.Datetime.now(), days=self.days_stuck_threshold)),
        ], order='write_date asc', limit=100)

        html = f"""
        <div class="o_outlook_sync_analysis">
            <h2>🔒 Événements bloqués (need_sync_m &gt; {self.days_stuck_threshold} jours)</h2>
            <p><strong>Date:</strong> {self.analysis_date}</p>
            <p><strong>Événements trouvés:</strong> {len(events)} (limité à 100)</p>

            <table class="table table-striped table-sm">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Événement</th>
                        <th>Date début</th>
                        <th>Utilisateur</th>
                        <th class="text-right">Jours bloqué</th>
                        <th>Microsoft ID</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
        """

        markdown_lines = [
            f"# Événements bloqués",
            f"",
            f"**Date:** {self.analysis_date}",
            f"**Seuil:** >{self.days_stuck_threshold} jours",
            f"**Événements trouvés:** {len(events)}",
            f"",
            f"| ID | Événement | Date début | Utilisateur | Jours | Microsoft ID |",
            f"|----|-----------|------------|-------------|-------|--------------|",
        ]

        for event in events:
            days_stuck = (fields.Datetime.now() - event.write_date).days if event.write_date else 0
            user_name = event.user_id.name if event.user_id else 'N/A'
            ms_id = (event.microsoft_id[:20] + '...') if event.microsoft_id else 'N/A'

            html += f"""
                    <tr>
                        <td>{event.id}</td>
                        <td>{event.name}</td>
                        <td>{event.start.strftime('%Y-%m-%d %H:%M') if event.start else 'N/A'}</td>
                        <td>{user_name}</td>
                        <td class="text-right text-danger">{days_stuck}</td>
                        <td><small>{ms_id}</small></td>
                        <td>
                            <a href="#" onclick="odoo.action_manager.do_action({{
                                'type': 'ir.actions.act_window',
                                'res_model': 'calendar.event',
                                'res_id': {event.id},
                                'views': [[false, 'form']],
                                'target': 'current'
                            }}); return false;">
                                <i class="fa fa-external-link"></i>
                            </a>
                        </td>
                    </tr>
            """

            markdown_lines.append(
                f"| {event.id} | {event.name} | {event.start.strftime('%Y-%m-%d') if event.start else 'N/A'} | "
                f"{user_name} | {days_stuck} | {ms_id} |"
            )

        html += """
                </tbody>
            </table>
        </div>
        """

        return {
            'html': html,
            'markdown': '\n'.join(markdown_lines),
            **stats
        }

    def _analyze_extreme_future(self):
        """Analyse des récurrences avec dates anormales"""
        stats = self._get_base_stats()

        events = self.env['calendar.event'].search([
            ('stop', '>', f'{self.future_year_threshold}-01-01'),
        ], order='stop desc', limit=100)

        html = f"""
        <div class="o_outlook_sync_analysis">
            <h2>📅 Récurrences avec dates futures extrêmes (&gt; {self.future_year_threshold})</h2>
            <p><strong>Date:</strong> {self.analysis_date}</p>
            <p><strong>Événements trouvés:</strong> {len(events)} (limité à 100)</p>

            <table class="table table-striped table-sm">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Événement</th>
                        <th>Date début</th>
                        <th>Date fin</th>
                        <th class="text-right">Année</th>
                        <th>Utilisateur</th>
                        <th>Récurrence</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
        """

        markdown_lines = [
            f"# Récurrences avec dates futures extrêmes",
            f"",
            f"**Date:** {self.analysis_date}",
            f"**Seuil:** >{self.future_year_threshold}",
            f"**Événements trouvés:** {len(events)}",
            f"",
            f"| ID | Événement | Date début | Date fin | Année | Utilisateur | Récurrence |",
            f"|----|-----------|------------|----------|-------|-------------|------------|",
        ]

        for event in events:
            user_name = event.user_id.name if event.user_id else 'N/A'
            is_recur = '✓' if event.recurrence_id else ''
            year = event.stop.year if event.stop else 'N/A'

            html += f"""
                    <tr class="{'table-danger' if year > 5000 else 'table-warning'}">
                        <td>{event.id}</td>
                        <td>{event.name}</td>
                        <td>{event.start.strftime('%Y-%m-%d') if event.start else 'N/A'}</td>
                        <td>{event.stop.strftime('%Y-%m-%d') if event.stop else 'N/A'}</td>
                        <td class="text-right text-danger"><strong>{year}</strong></td>
                        <td>{user_name}</td>
                        <td>{is_recur}</td>
                        <td>
                            <a href="#" onclick="odoo.action_manager.do_action({{
                                'type': 'ir.actions.act_window',
                                'res_model': 'calendar.event',
                                'res_id': {event.id},
                                'views': [[false, 'form']],
                                'target': 'current'
                            }}); return false;">
                                <i class="fa fa-external-link"></i>
                            </a>
                        </td>
                    </tr>
            """

            markdown_lines.append(
                f"| {event.id} | {event.name} | {event.start.strftime('%Y-%m-%d') if event.start else 'N/A'} | "
                f"{event.stop.strftime('%Y-%m-%d') if event.stop else 'N/A'} | {year} | {user_name} | {is_recur} |"
            )

        html += """
                </tbody>
            </table>

            <div class="alert alert-warning mt-3">
                <strong>Recommandation:</strong> Ces événements devraient être supprimés et recréés dans Outlook avec une date de fin raisonnable.
            </div>
        </div>
        """

        return {
            'html': html,
            'markdown': '\n'.join(markdown_lines),
            **stats
        }

    def _analyze_user_comparison(self):
        """Comparaison entre utilisateurs"""
        stats = self._get_base_stats()

        users = self.env['res.users'].search([
            ('microsoft_calendar_rtoken', '!=', False),
        ])

        # Statistiques par utilisateur
        user_stats = []
        for user in users:
            events = self.env['calendar.event'].search([
                ('partner_ids.user_ids', 'in', user.id),
            ])

            synced = events.filtered(lambda e: e.microsoft_id)
            need_sync = events.filtered(lambda e: e.need_sync_m)
            stuck = need_sync.filtered(
                lambda e: e.write_date and (fields.Datetime.now() - e.write_date).days > self.days_stuck_threshold
            )

            user_stats.append({
                'user': user,
                'total': len(events),
                'synced': len(synced),
                'need_sync': len(need_sync),
                'stuck': len(stuck),
                'sync_rate': (len(synced) / len(events) * 100) if events else 0,
            })

        # Trier par taux de synchronisation
        user_stats.sort(key=lambda x: x['sync_rate'])

        html = f"""
        <div class="o_outlook_sync_analysis">
            <h2>📊 Comparaison entre utilisateurs</h2>
            <p><strong>Date:</strong> {self.analysis_date}</p>

            <div class="row">
                <div class="col-md-6">
                    <h4>Meilleurs taux de synchronisation</h4>
                    <table class="table table-sm">
                        <thead>
                            <tr><th>Utilisateur</th><th class="text-right">Taux</th><th class="text-right">Synced/Total</th></tr>
                        </thead>
                        <tbody>
        """

        # Top 5 meilleurs
        for stat in user_stats[-5:][::-1]:
            html += f"""
                            <tr class="table-success">
                                <td>{stat['user'].name}</td>
                                <td class="text-right">{stat['sync_rate']:.1f}%</td>
                                <td class="text-right">{stat['synced']}/{stat['total']}</td>
                            </tr>
            """

        html += """
                        </tbody>
                    </table>
                </div>
                <div class="col-md-6">
                    <h4>Utilisateurs problématiques</h4>
                    <table class="table table-sm">
                        <thead>
                            <tr><th>Utilisateur</th><th class="text-right">Taux</th><th class="text-right">Bloqués</th></tr>
                        </thead>
                        <tbody>
        """

        # Top 5 problématiques
        for stat in user_stats[:5]:
            html += f"""
                            <tr class="table-danger">
                                <td>{stat['user'].name}</td>
                                <td class="text-right">{stat['sync_rate']:.1f}%</td>
                                <td class="text-right">{stat['stuck']}</td>
                            </tr>
            """

        html += """
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        """

        # Markdown
        markdown_lines = [
            f"# Comparaison entre utilisateurs",
            f"",
            f"**Date:** {self.analysis_date}",
            f"",
            f"## Meilleurs taux de synchronisation",
            f"",
            f"| Utilisateur | Taux | Synced/Total |",
            f"|-------------|------|--------------|",
        ]

        for stat in user_stats[-5:][::-1]:
            markdown_lines.append(f"| {stat['user'].name} | {stat['sync_rate']:.1f}% | {stat['synced']}/{stat['total']} |")

        markdown_lines.extend([
            f"",
            f"## Utilisateurs problématiques",
            f"",
            f"| Utilisateur | Taux | Bloqués |",
            f"|-------------|------|---------|",
        ])

        for stat in user_stats[:5]:
            markdown_lines.append(f"| {stat['user'].name} | {stat['sync_rate']:.1f}% | {stat['stuck']} |")

        return {
            'html': html,
            'markdown': '\n'.join(markdown_lines),
            **stats
        }

    def action_view_report(self):
        """Affiche le rapport généré"""
        self.ensure_one()
        if not self.report_id:
            return

        return {
            'name': _('Rapport d\'analyse'),
            'type': 'ir.actions.act_window',
            'res_model': 'microsoft.sync.report',
            'res_id': self.report_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_export_report(self):
        """Exporte le rapport en markdown"""
        self.ensure_one()
        if self.report_id:
            return self.report_id.action_save_to_file()
