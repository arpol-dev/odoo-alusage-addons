#!/usr/bin/env python3
"""
Script d'analyse de la synchronisation Outlook en production

Usage:
    python production_analysis.py --database your_db --output report.md

Options:
    --database: Nom de la base de données Odoo
    --output: Fichier de sortie pour le rapport (défaut: outlook_sync_report.md)
    --config: Chemin du fichier de configuration Odoo (défaut: /etc/odoo/odoo.conf)
"""

import argparse
import sys
import os
from datetime import datetime, timedelta

# Ajouter le chemin d'Odoo
sys.path.append('/usr/lib/python3/dist-packages')

try:
    import odoo
    from odoo import api
except ImportError:
    print("Erreur: Impossible d'importer Odoo. Vérifier l'installation.")
    sys.exit(1)


def analyze_database(db_name, config_file='/etc/odoo/odoo.conf'):
    """Analyse la base de données et retourne les statistiques"""

    # Initialiser Odoo
    odoo.tools.config.parse_config(['-c', config_file, '-d', db_name])

    with odoo.api.Environment.manage():
        registry = odoo.registry(db_name)
        with registry.cursor() as cr:
            uid = odoo.SUPERUSER_ID
            env = api.Environment(cr, uid, {})

            stats = {
                'date': datetime.now(),
                'database': db_name,
                'users': [],
                'anomalies': [],
                'stuck_events': [],
                'extreme_future': [],
            }

            # Récupérer les utilisateurs avec sync Outlook
            users = env['res.users'].search([
                ('microsoft_calendar_rtoken', '!=', False),
            ])

            for user in users:
                # Événements de l'utilisateur
                events = env['calendar.event'].search([
                    ('partner_ids.user_ids', 'in', user.id),
                ])

                synced = events.filtered(lambda e: e.microsoft_id)
                need_sync = events.filtered(lambda e: e.need_sync_m)
                stuck = need_sync.filtered(
                    lambda e: e.write_date and (datetime.now() - e.write_date).days > 7
                )

                user_stats = {
                    'id': user.id,
                    'name': user.name,
                    'login': user.login,
                    'email': user.email,
                    'total_events': len(events),
                    'synced': len(synced),
                    'need_sync': len(need_sync),
                    'stuck': len(stuck),
                    'last_sync': user.microsoft_last_sync_date,
                }

                stats['users'].append(user_stats)

                # Collecter les événements bloqués
                for event in stuck[:10]:  # Limite à 10 par utilisateur
                    stats['stuck_events'].append({
                        'user': user.name,
                        'event_name': event.name,
                        'start': event.start,
                        'microsoft_id': event.microsoft_id,
                        'days_stuck': (datetime.now() - event.write_date).days if event.write_date else 0,
                        'write_date': event.write_date,
                    })

            # Détecter les récurrences anormales
            extreme_events = env['calendar.event'].search([
                ('stop', '>', f'{datetime.now().year + 10}-01-01'),
            ], limit=50)

            for event in extreme_events:
                stats['extreme_future'].append({
                    'id': event.id,
                    'name': event.name,
                    'start': event.start,
                    'stop': event.stop,
                    'year': event.stop.year if event.stop else None,
                    'user': event.user_id.name if event.user_id else 'N/A',
                    'recurrence': bool(event.recurrence_id),
                })

            # Statistiques globales
            all_events = env['calendar.event'].search([])
            stats['global'] = {
                'total_events': len(all_events),
                'synced_events': len(all_events.filtered(lambda e: e.microsoft_id)),
                'need_sync_events': len(all_events.filtered(lambda e: e.need_sync_m)),
                'stuck_events': len(all_events.filtered(
                    lambda e: e.need_sync_m and e.write_date and (datetime.now() - e.write_date).days > 7
                )),
                'extreme_future_events': len(extreme_events),
            }

            return stats


def generate_markdown_report(stats):
    """Génère un rapport markdown à partir des statistiques"""

    lines = [
        "# Rapport d'analyse Outlook Sync",
        "",
        f"**Date:** {stats['date']}",
        f"**Base de données:** {stats['database']}",
        "",
        "## Statistiques globales",
        "",
        f"- Total événements: {stats['global']['total_events']}",
        f"- Synchronisés: {stats['global']['synced_events']}",
        f"- À synchroniser (need_sync_m): {stats['global']['need_sync_events']}",
        f"- Bloqués (>7 jours): {stats['global']['stuck_events']}",
        f"- Futur extrême (>10 ans): {stats['global']['extreme_future_events']}",
        "",
        "## Utilisateurs",
        "",
        "| Utilisateur | Login | Total | Synced | Need Sync | Bloqués | Dernière sync |",
        "|-------------|-------|-------|--------|-----------|---------|---------------|",
    ]

    for user in sorted(stats['users'], key=lambda u: -u['stuck']):
        last_sync = user['last_sync'].strftime('%Y-%m-%d %H:%M') if user['last_sync'] else 'N/A'
        lines.append(
            f"| {user['name']} | {user['login']} | {user['total_events']} | "
            f"{user['synced']} | {user['need_sync']} | {user['stuck']} | {last_sync} |"
        )

    if stats['stuck_events']:
        lines.extend([
            "",
            "## ⚠️ Événements bloqués (need_sync_m > 7 jours)",
            "",
            "| Utilisateur | Événement | Date début | Jours | Microsoft ID |",
            "|-------------|-----------|------------|-------|--------------|",
        ])

        for event in sorted(stats['stuck_events'], key=lambda e: -e['days_stuck']):
            start = event['start'].strftime('%Y-%m-%d %H:%M') if event['start'] else 'N/A'
            ms_id = (event['microsoft_id'][:20] + '...') if event['microsoft_id'] else 'N/A'
            lines.append(
                f"| {event['user']} | {event['event_name']} | {start} | "
                f"{event['days_stuck']} | {ms_id} |"
            )

    if stats['extreme_future']:
        lines.extend([
            "",
            "## ⚠️ Événements avec dates futures extrêmes",
            "",
            "| ID | Événement | Date début | Date fin | Année | Utilisateur | Récurrence |",
            "|-----|-----------|------------|----------|-------|-------------|------------|",
        ])

        for event in sorted(stats['extreme_future'], key=lambda e: -e['year'] if e['year'] else 0):
            start = event['start'].strftime('%Y-%m-%d') if event['start'] else 'N/A'
            stop = event['stop'].strftime('%Y-%m-%d') if event['stop'] else 'N/A'
            recur = '✓' if event['recurrence'] else ''
            lines.append(
                f"| {event['id']} | {event['name']} | {start} | {stop} | "
                f"{event['year']} | {event['user']} | {recur} |"
            )

    lines.extend([
        "",
        "## Actions recommandées",
        "",
        "### 1. Installer le module outlook_sync_analyzer",
        "",
        "```bash",
        "# Dans Odoo",
        "Apps > Update Apps List > Chercher 'Outlook Sync Analyzer' > Install",
        "```",
        "",
        "### 2. Configurer les limites de synchronisation",
        "",
        "Aller dans **Paramètres > Outlook Sync Analyzer**:",
        "- Plage de synchronisation: 30 jours (au lieu de 365)",
        "- Borne inférieure: 30 jours",
        "- Année future max: 2030",
        "",
        "### 3. Activer le logging",
        "",
        "- Activer 'Logging détaillé'",
        "- Activer 'Générer des rapports markdown'",
        "- Configurer le chemin: `/var/log/odoo/outlook_sync`",
        "",
        "### 4. Nettoyer les événements anormaux",
        "",
        "```sql",
        "-- ATTENTION: Faire un backup avant !",
        "",
        "-- Supprimer les événements avec dates > 2030",
        "DELETE FROM calendar_event WHERE EXTRACT(YEAR FROM stop) > 2030;",
        "",
        "-- Réinitialiser les événements bloqués > 30 jours",
        "UPDATE calendar_event",
        "SET need_sync_m = false",
        "WHERE need_sync_m = true",
        "AND write_date < NOW() - INTERVAL '30 days';",
        "```",
        "",
        "### 5. Analyser les utilisateurs problématiques",
        "",
        f"Les utilisateurs avec le plus d'événements bloqués:",
    ])

    # Top 5 des utilisateurs problématiques
    top_users = sorted(stats['users'], key=lambda u: -u['stuck'])[:5]
    for i, user in enumerate(top_users, 1):
        if user['stuck'] > 0:
            lines.append(f"{i}. **{user['name']}** ({user['login']}): {user['stuck']} événements bloqués")

    lines.extend([
        "",
        "## Requêtes SQL utiles",
        "",
        "### Événements bloqués détaillés",
        "",
        "```sql",
        "SELECT",
        "    ce.id,",
        "    ce.name,",
        "    ce.start,",
        "    ce.microsoft_id,",
        "    ru.name as user_name,",
        "    ce.write_date,",
        "    EXTRACT(DAY FROM NOW() - ce.write_date) as days_stuck",
        "FROM calendar_event ce",
        "JOIN calendar_event_res_partner_rel cepr ON cepr.calendar_event_id = ce.id",
        "JOIN res_partner rp ON rp.id = cepr.res_partner_id",
        "JOIN res_users ru ON ru.partner_id = rp.id",
        "WHERE ce.need_sync_m = true",
        "AND ce.write_date < NOW() - INTERVAL '7 days'",
        "ORDER BY days_stuck DESC;",
        "```",
        "",
        "### Récurrences anormales",
        "",
        "```sql",
        "SELECT",
        "    ce.id,",
        "    ce.name,",
        "    ce.start,",
        "    ce.stop,",
        "    EXTRACT(YEAR FROM ce.stop) as year_stop,",
        "    ce.recurrence_id,",
        "    cr.rrule",
        "FROM calendar_event ce",
        "LEFT JOIN calendar_recurrence cr ON cr.id = ce.recurrence_id",
        "WHERE EXTRACT(YEAR FROM ce.stop) > 2030",
        "ORDER BY ce.stop DESC;",
        "```",
    ])

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Analyse la synchronisation Outlook en production')
    parser.add_argument('--database', '-d', required=True, help='Nom de la base de données')
    parser.add_argument('--output', '-o', default='outlook_sync_report.md', help='Fichier de sortie')
    parser.add_argument('--config', '-c', default='/etc/odoo/odoo.conf', help='Fichier de configuration Odoo')

    args = parser.parse_args()

    print(f"Analyse de la base de données: {args.database}")
    print("Cela peut prendre quelques minutes...")

    try:
        stats = analyze_database(args.database, args.config)
        report = generate_markdown_report(stats)

        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"\n✓ Rapport généré: {args.output}")
        print(f"\nRésumé:")
        print(f"  - Utilisateurs: {len(stats['users'])}")
        print(f"  - Total événements: {stats['global']['total_events']}")
        print(f"  - Événements bloqués: {stats['global']['stuck_events']}")
        print(f"  - Futur extrême: {stats['global']['extreme_future_events']}")

        if stats['global']['stuck_events'] > 0:
            print(f"\n⚠️  ATTENTION: {stats['global']['stuck_events']} événements bloqués détectés !")

        if stats['global']['extreme_future_events'] > 0:
            print(f"⚠️  ATTENTION: {stats['global']['extreme_future_events']} événements avec dates extrêmes !")

    except Exception as e:
        print(f"\n❌ Erreur lors de l'analyse: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
