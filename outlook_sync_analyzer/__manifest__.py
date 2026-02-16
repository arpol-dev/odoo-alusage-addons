{
    'name': 'Outlook Sync Analyzer',
    'version': '18.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Analyse et suivi détaillé de la synchronisation Outlook',
    'description': '''
Outlook Sync Analyzer
=====================

Ce module permet de :
- Tracer en détail toutes les opérations de synchronisation Outlook
- Générer des rapports markdown sur chaque synchronisation
- Identifier les événements bloqués en need_sync_m
- Analyser les problèmes de récurrences
- Fournir un rapport par compte utilisateur
- Limiter la récupération d'anciens événements

Fonctionnalités:
----------------
* Logs détaillés de synchronisation avec timestamps
* Rapports markdown automatiques à chaque synchro
* Dashboard de monitoring des synchronisations
* Analyse des événements need_sync_m
* Détection des récurrences anormales (dates futures extrêmes)
* Configuration des limites de synchronisation par date
    ''',
    'author': 'Nicolas JEUDY - ALUSAGE SAS',
    'contributors': ['Sudokeys', 'ArPol'],
    'website': 'https://github.com/alusage',
    'license': 'LGPL-3',
    'depends': [
        'microsoft_calendar',
        'base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/microsoft_sync_log_views.xml',
        'views/microsoft_sync_report_views.xml',
        'views/outlook_sync_analysis_wizard_views.xml',
        'views/calendar_event_views.xml',
        'views/res_config_settings_views.xml',
        'data/ir_cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
