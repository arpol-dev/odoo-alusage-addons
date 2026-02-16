# Outlook Sync Analyzer

Module d'analyse et traçage pour la synchronisation Outlook Calendar dans Odoo 17.0 Enterprise

---

## 📑 Table des matières

- [Description](#description)
- [Problèmes résolus](#problèmes-résolus)
- [Installation](#installation)
- [Configuration](#configuration)
- [Utilisation](#utilisation)
  - [Assistant d'analyse interactif](#assistant-danalyse-interactif)
  - [Logs de synchronisation](#logs-de-synchronisation)
  - [Rapports automatiques du cron](#rapports-automatiques-du-cron)
  - [Événements bloqués](#événements-bloqués)
  - [Récurrences anormales](#récurrences-anormales)
- [Scripts de production](#scripts-de-production)
- [API et développement](#api-et-développement)
- [Requêtes SQL utiles](#requêtes-sql-utiles)
- [Dépannage](#dépannage)
- [Guide de test](#guide-de-test)
- [Support](#support)

---

## Description

Ce module résout les **5 problèmes majeurs** de synchronisation Outlook Calendar en fournissant :

- ✅ **Traçage détaillé** de toutes les opérations de sync
- ✅ **Rapports markdown automatiques** à chaque exécution du cron
- ✅ **Détection d'anomalies** (événements bloqués, récurrences 9992, etc.)
- ✅ **Assistant d'analyse interactif** pour diagnostics rapides
- ✅ **Configuration avancée** des limites de synchronisation
- ✅ **Dashboard de monitoring** accessible depuis l'interface Odoo

---

## Problèmes résolus

### 1. 🔴 Récurrences jusqu'en l'année 9992

**Symptôme :** Des événements récurrents sont créés avec des dates extrêmes (jusqu'en 9992)

**Cause :** Récurrences annuelles "sans fin" × `MAX_RECURRENT_EVENT=720` = 720 occurrences sur 720 ans

**Solution apportée :**
- Détection automatique des événements > année seuil (défaut: 2030)
- Menu dédié "Futur extrême" pour identifier et nettoyer
- Assistant d'analyse pour diagnostiquer le problème

### 2. 🔴 Événements bloqués en need_sync_m

**Symptôme :** 256+ événements restent en `need_sync_m=True` sans jamais se synchroniser

**Causes :**
- Décorateur `@after_commit` qui masque les exceptions
- Microsoft_id différent entre organisateur et participant (Issue #148011)
- Token expiré ou révoqué

**Solution apportée :**
- Logging complet de toutes les tentatives de sync
- Détection des événements bloqués > 7 jours
- Historique de sync par événement pour diagnostic
- Actions de resync forcé

### 3. 🔴 Absence de traçabilité

**Symptôme :** Impossible de savoir ce qui se passe lors des synchronisations

**Solution apportée :**
- Logging complet avec timestamps, durées, codes API
- Capture des exceptions et messages d'erreur détaillés
- Rapports markdown générés automatiquement
- Dashboard de consultation des logs

### 4. 🔴 Synchronisation d'événements trop anciens

**Symptôme :** Synchronisation d'événements de plus d'1 an (défaut: 365 jours)

**Solution apportée :**
- Configuration du paramètre `microsoft_calendar.sync.range_days` (recommandé: 30)
- Configuration du paramètre `microsoft_calendar.sync.lower_bound_range`
- Date de première synchronisation configurable
- Détection des événements anciens synchronisés

### 5. 🔴 Pas de rapport par compte utilisateur

**Symptôme :** Impossible d'identifier quel utilisateur a des problèmes

**Solution apportée :**
- Rapports par utilisateur accessibles depuis Paramètres > Utilisateurs
- Rapport global comparatif tous utilisateurs
- Assistant d'analyse "Par utilisateur" et "Comparaison utilisateurs"
- Logs filtrables par utilisateur

---

## Installation

### Prérequis

- Odoo Enterprise
- Module `microsoft_calendar` installé et configuré
- Compte(s) Microsoft configuré(s) pour la synchronisation

### Installation du module

```bash
# 1. Copier le module dans addons_path
cp -r outlook_sync_analyzer /path/to/odoo/addons/

# 2. Redémarrer Odoo
sudo systemctl restart odoo

# 3. Mettre à jour la liste des modules
# Interface Odoo > Apps > Update Apps List

# 4. Installer le module
# Apps > Search "Outlook Sync Analyzer" > Install
```

### Installation des scripts (optionnel)

Les scripts de production permettent d'analyser une base sans installer le module :

```bash
cd outlook_sync_analyzer/scripts

# Installation des dépendances Python
pip3 install psycopg2-binary

# Rendre les scripts exécutables
chmod +x analyze.sh
```

---

## Configuration

### Paramètres > Outlook Sync Analyzer

#### Logging

| Paramètre | Description | Recommandé |
|-----------|-------------|------------|
| **Activer le logging détaillé** | Capture toutes les opérations de sync | ✅ OUI |
| **Générer des rapports markdown** | Crée automatiquement des rapports à chaque sync | ✅ OUI |
| **Chemin des rapports** | Répertoire serveur pour sauvegarder les rapports | `/var/log/odoo/outlook_sync` |

**Configuration du répertoire :**
```bash
sudo mkdir -p /var/log/odoo/outlook_sync
sudo chown odoo:odoo /var/log/odoo/outlook_sync
sudo chmod 755 /var/log/odoo/outlook_sync
```

#### Limites de synchronisation

| Paramètre | Défaut | Recommandé | Description |
|-----------|--------|------------|-------------|
| **Plage de synchronisation** | 365 jours | **30 jours** | Jours dans le passé/futur à synchroniser |
| **Borne inférieure** | - | **30 jours** | Évite de mettre à jour des événements trop anciens |
| **Limite année future** | 2030 | 2030 | Détecte les récurrences anormales |
| **Limite événements anciens** | 365 jours | 365 jours | Alerte si sync d'événements trop anciens |
| **Date première synchronisation** | - | Date souhaitée | Sync uniquement les événements créés après cette date |

**Configuration via paramètres système :**
```python
# Paramètres > Technique > Paramètres système
microsoft_calendar.sync.range_days = 30
microsoft_calendar.sync.lower_bound_range = 30
outlook_sync_analyzer.future_year_limit = 2030
outlook_sync_analyzer.old_event_limit_days = 365
microsoft_calendar.sync.first_synchronization_date = 2024-01-01 00:00:00
```

---

## Utilisation

### 🎯 Accès rapide

**Menu principal : Calendrier > Sync Outlook**

- 🔍 **Analyse de synchronisation** - Assistant d'analyse interactif
- 📋 **Logs de synchronisation** - Historique détaillé
- 📄 **Rapports** - Rapports markdown générés
- ⚠️ **Événements à synchroniser** - Liste des need_sync_m
- 🔒 **Événements bloqués** - Problèmes détectés (>7 jours)
- 📅 **Futur extrême** - Récurrences anormales (>2030)

---

### Assistant d'analyse interactif

**Accès :** Calendrier > Sync Outlook > Analyse de synchronisation

#### Types d'analyses disponibles

##### 1. Analyse globale

Vue d'ensemble complète de la synchronisation :
- Statistiques générales (total, synced, need_sync, stuck, extreme_future)
- Nombre d'utilisateurs configurés
- Alertes sur les problèmes critiques
- Recommandations d'actions

**Quand l'utiliser :** Pour un diagnostic rapide de l'état global (quotidien)

##### 2. Par utilisateur

Analyse détaillée de chaque utilisateur :
- Liste de tous les utilisateurs avec sync Outlook
- Pour chaque utilisateur : total, synced, need_sync, bloqués, dernière sync
- Tri par nombre d'événements bloqués (décroissant)

**Quand l'utiliser :** Pour identifier quels utilisateurs ont des problèmes

##### 3. Événements bloqués

Liste détaillée des événements en need_sync_m depuis plus de X jours :
- ID, nom, date début, utilisateur
- Nombre de jours bloqué
- Microsoft ID
- Lien direct vers l'événement

**Quand l'utiliser :** Pour diagnostiquer les événements qui ne se synchronisent jamais

##### 4. Récurrences anormales

Liste des événements avec dates futures extrêmes (> année seuil) :
- ID, nom, dates début/fin, année
- Utilisateur, indicateur de récurrence
- Lien direct vers l'événement

**Quand l'utiliser :** Pour identifier les récurrences créées jusqu'en 9992

##### 5. Comparaison utilisateurs

Comparatif entre utilisateurs :
- Top 5 meilleurs taux de synchronisation
- Top 5 utilisateurs problématiques
- Taux de sync et nombre de bloqués

**Quand l'utiliser :** Pour identifier rapidement les comptes à traiter en priorité

#### Paramètres de l'analyse

- **Seuil jours bloqués** : Par défaut 7 jours
- **Seuil année future** : Par défaut 2030
- **Utilisateurs** : Sélectionner des utilisateurs spécifiques ou tous

#### Résultats

Les résultats sont affichés avec :
- **Onglet Résultats** : Vue HTML formatée avec tableaux colorés
- **Onglet Markdown** : Version texte exportable

**Actions disponibles :**
- **Voir le rapport** : Ouvre le rapport dans l'interface rapports
- **Exporter** : Sauvegarde le rapport en markdown sur le serveur

---

### Logs de synchronisation

**Accès :** Calendrier > Sync Outlook > Logs de synchronisation

#### Filtres disponibles

- Par statut : Erreurs, Timeouts, Succès
- Par utilisateur
- Par opération (insert, patch, delete, sync M2O, O2M)
- Par date : Aujourd'hui, Cette semaine

#### Informations dans les logs

Chaque log contient :
- Date et heure exacte
- Utilisateur concerné
- Type d'opération
- Statut (succès/erreur/timeout)
- Durée en millisecondes
- Compteurs : créés, mis à jour, supprimés, erreurs
- Need_sync_m avant/après (pour voir l'évolution)
- Détection d'anomalies
- Messages d'erreur détaillés

#### Générer un rapport depuis un log

Sur un log, cliquer sur **"Générer rapport MD"** pour créer un rapport markdown de ce log spécifique.

---

### Rapports automatiques du cron

Le module intercepte automatiquement le cron de synchronisation Outlook et génère un rapport markdown à chaque exécution.

#### Configuration

**Paramètres > Outlook Sync Analyzer**
- ✅ Activer le logging détaillé
- ✅ Générer des rapports markdown
- 📁 Chemin des rapports : `/var/log/odoo/outlook_sync`

**Le cron de synchronisation** (aucune modification nécessaire) :
- **Nom :** Calendar Synchro - Synchronize all calendars
- **Fréquence :** Toutes les 5 minutes (par défaut)
- **Modèle :** res.users
- **Méthode :** `_sync_all_microsoft_calendar()`

#### Contenu des rapports automatiques

Chaque exécution du cron génère un rapport markdown avec :

1. **En-tête** : Date, durée totale
2. **Synthèse** : Tableaux avant/après (événements totaux, need_sync, créés, synchronisés)
3. **Utilisateurs** : Nombre de succès/erreurs
4. **Détails par utilisateur** : Tableau avec durée, événements, need_sync par utilisateur
5. **Erreurs** : Détails des erreurs rencontrées (si applicable)
6. **Anomalies** : Événements bloqués, récurrences extrêmes détectés
7. **Recommandations** : Actions à entreprendre
8. **Performance** : Statistiques de temps (total, moyen, plus rapide, plus lent)

#### Exemple de rapport (succès)

```markdown
# Rapport de synchronisation Outlook - Tâche planifiée

**Date d'exécution:** 2025-11-27 10:15:00
**Durée totale:** 12.3s
**Durée de synchronisation (utilisateurs):** 11.8s

## Synthèse

| Métrique | Avant | Après | Delta |
|----------|-------|-------|-------|
| **Événements totaux** | 4520 | 4525 | +5 |
| **Need sync global** | 256 | 230 | -26 |
| **Événements créés** | - | 5 | +5 |
| **Événements synchronisés** | - | 26 | +26 |

## Utilisateurs

- Total utilisateurs: 15
- ✅ Succès: 15

## Détails par utilisateur

| Utilisateur | Statut | Durée (ms) | Total | Créés | Need Sync | Synchronisés |
|-------------|--------|------------|-------|-------|-----------|--------------|
| Jean Dupont | ✓ | 3245 | 450 | +2 | 15 (-5) | 5 |
| Marie Martin | ✓ | 2890 | 380 | +1 | 20 (-3) | 3 |
...

## 📋 Recommandations

- ✅ **Aucune action requise** : La synchronisation fonctionne correctement

## ⏱️ Performance

- Temps total: 12.3s
- Temps de synchronisation: 11.8s
- Temps moyen par utilisateur: 0.8s
- Plus rapide: Sophie Leroy (1980ms)
- Plus lent: Jean Dupont (3245ms)
```

#### Emplacement des rapports

Les rapports sont sauvegardés automatiquement dans le répertoire configuré :

```
/var/log/odoo/outlook_sync/
├── sync_report_2025-11-27_10-15-00.md
├── sync_report_2025-11-27_10-20-00.md
├── sync_report_2025-11-27_10-25-00.md
...
```

**Format du nom de fichier :** `sync_report_YYYY-MM-DD_HH-MM-SS.md`

---

### Événements bloqués

**Accès :** Calendrier > Sync Outlook > Événements bloqués

#### Vue des événements stuck

Affiche uniquement les événements bloqués depuis plus de 7 jours (configurable).

**Indicateurs :**
- Ligne en rouge si bloqué > 7 jours
- Badge d'état "Bloqué" sur l'événement
- Nombre de jours bloqué visible

#### Diagnostiquer un événement bloqué

1. Ouvrir l'événement
2. Cliquer sur **"Historique sync"**
3. Consulter les logs :
   - Chercher les erreurs récurrentes
   - Vérifier les codes réponse API
   - Identifier le pattern (timeout, 404, 401, etc.)

#### Solutions communes

**Problème de token :**
```
Erreur: 401 Unauthorized
Solution: Paramètres > Utilisateurs > Calendrier > Déconnecter/Reconnecter Outlook
```

**Problème d'organisateur (Issue #148011) :**
```
Erreur: 404 Not Found
Microsoft ID: AAMkAGI... (d'un autre utilisateur)
Solution: Supprimer et recréer l'événement, ou contacter l'organisateur
```

**Timeout récurrent :**
```
Erreur: Timeout after 3000ms
Solution: Vérifier la connexion, augmenter le timeout
```

---

### Récurrences anormales

**Accès :** Calendrier > Sync Outlook > Futur extrême

#### Vue des événements > année seuil

Affiche les événements avec des dates au-delà de l'année seuil (défaut: 2030).

**Causes communes :**
- Récurrences annuelles "sans fin" créées dans Outlook
- `MAX_RECURRENT_EVENT=720` génère 720 occurrences
- Récurrence annuelle × 720 = année 2745 à 9992 !

#### Résoudre le problème

**Option 1 : Supprimer et recréer (recommandé)**

1. Identifier l'événement récurrent dans Outlook
2. Le supprimer dans Outlook (supprimera dans Odoo à la prochaine sync)
3. Le recréer avec une date de fin raisonnable (ex: 10 ans)

**Option 2 : Nettoyage en masse (ATTENTION : Backup d'abord !)**

```sql
-- Supprimer tous les événements > 2030
DELETE FROM calendar_event WHERE EXTRACT(YEAR FROM stop) > 2030;
```

---

## Scripts de production

Pour analyser une base de données **sans installer le module**, utilisez les scripts fournis.

### production_analysis.py

Script Python pour génér des rapports markdown depuis n'importe quelle base Odoo.

#### Usage

```bash
cd outlook_sync_analyzer/scripts

python3 production_analysis.py \
  --host localhost \
  --port 5432 \
  --database prod_db \
  --user odoo \
  --password odoo \
  --output /tmp/report.md
```

#### Paramètres

| Paramètre | Description | Défaut |
|-----------|-------------|--------|
| `--host` | Hôte PostgreSQL | localhost |
| `--port` | Port PostgreSQL | 5432 |
| `--database` | Nom de la base | (requis) |
| `--user` | Utilisateur PostgreSQL | odoo |
| `--password` | Mot de passe | (requis) |
| `--output` | Fichier markdown de sortie | report.md |

#### Exemple de sortie

Le script génère un rapport markdown avec :
- Statistiques globales
- Événements bloqués (need_sync_m > 7 jours)
- Récurrences anormales (année > 2030)
- Distribution par utilisateur
- Recommandations

### analyze.sh

Script Bash pour analyse rapide avec sortie colorée dans le terminal.

#### Usage

```bash
cd outlook_sync_analyzer/scripts

./analyze.sh database_name [postgres_user]
```

#### Exemple

```bash
./analyze.sh prod_db odoo
```

#### Sortie

```
=== Outlook Sync Analyzer - Production Database ===
Database: prod_db

📊 Global Statistics
  Total events: 4520
  Need sync: 256
  Stuck (>7 days): 45
  Extreme future (>2030): 120

🔴 Top 10 stuck events
  ID    | Name              | Days stuck | User
  ------|-------------------|------------|------------
  12345 | Congé 2025        | 45         | John Doe
  ...

⚠️  Extreme future events (>2030)
  ID    | Name              | Year  | User
  ------|-------------------|-------|------------
  98765 | Anniversaire      | 9992  | Jane Doe
  ...
```

---

## API et développement

### Context manager pour logging

```python
from odoo.addons.outlook_sync_analyzer.models.microsoft_sync_log import MicrosoftSyncLogContext

# Dans votre code
with MicrosoftSyncLogContext(
    self.env,
    self.env.user,
    'sync_m2o',
    events_count=len(events)
) as log_ctx:
    # Votre code de synchronisation
    result = do_sync()

    # Mise à jour des statistiques
    log_ctx.update_stats(
        events_created=10,
        events_updated=20
    )

    # Signaler une anomalie
    if problem:
        log_ctx.add_anomaly('stuck_need_sync', 'Détails du problème...')
```

### Générer un rapport manuel

```python
# Pour un utilisateur
user = self.env.user
action = user.action_view_outlook_sync_report()

# Rapport global
settings = self.env['res.config.settings'].create({})
action = settings.action_analyze_all_users()
```

### Analyser les need_sync_m

```python
# Via le menu ou programmatiquement
events = self.env['calendar.event'].search([
    ('need_sync_m', '=', True)
])
action = events.action_analyze_need_sync()
```

### Activer le logging dans le contexte

```python
# Dans votre code personnalisé
events = self.env['calendar.event'].with_context(
    outlook_sync_enable_logging=True,
    outlook_sync_generate_reports=True
).search([...])
```

---

## Requêtes SQL utiles

### Événements bloqués par utilisateur

```sql
SELECT
    ru.name,
    ru.login,
    COUNT(*) as count_stuck
FROM calendar_event ce
JOIN calendar_event_res_partner_rel cepr ON cepr.calendar_event_id = ce.id
JOIN res_partner rp ON rp.id = cepr.res_partner_id
JOIN res_users ru ON ru.partner_id = rp.id
WHERE ce.need_sync_m = true
AND ce.write_date < NOW() - INTERVAL '7 days'
GROUP BY ru.id, ru.name, ru.login
ORDER BY count_stuck DESC;
```

### Récurrences anormales

```sql
SELECT
    id,
    name,
    start,
    stop,
    EXTRACT(YEAR FROM stop) as year_stop
FROM calendar_event
WHERE EXTRACT(YEAR FROM stop) > 2030
ORDER BY stop DESC;
```

### Statistiques de sync journalières

```sql
SELECT
    DATE(create_date) as date,
    operation,
    status,
    COUNT(*) as count,
    AVG(duration_ms) as avg_duration,
    SUM(events_errors) as total_errors
FROM microsoft_sync_log
WHERE create_date >= NOW() - INTERVAL '30 days'
GROUP BY DATE(create_date), operation, status
ORDER BY date DESC, operation;
```

### Nettoyage des logs anciens

```sql
-- Supprimer les logs de plus de 90 jours
DELETE FROM microsoft_sync_log
WHERE create_date < NOW() - INTERVAL '90 days';

-- Supprimer les rapports associés
DELETE FROM microsoft_sync_report
WHERE log_id NOT IN (
    SELECT id FROM microsoft_sync_log
);
```

---

## Dépannage

### Aucun log n'est créé

**Cause :** Le logging n'est pas activé

**Solution :**
1. Vérifier : Paramètres > Outlook Sync Analyzer > ✅ Activer le logging
2. Si code personnalisé, ajouter le contexte :
```python
events.with_context(outlook_sync_enable_logging=True)
```

### Les rapports ne sont pas générés

**Cause :** La génération n'est pas activée ou problème de permissions

**Solution :**
1. Activer : Paramètres > Outlook Sync Analyzer > ✅ Générer des rapports markdown
2. Vérifier les permissions sur le répertoire :
```bash
sudo mkdir -p /var/log/odoo/outlook_sync
sudo chown odoo:odoo /var/log/odoo/outlook_sync
sudo chmod 755 /var/log/odoo/outlook_sync
```

### Événements bloqués en need_sync_m

**Diagnostic :**
1. Consulter **Calendrier > Sync Outlook > Événements bloqués**
2. Ouvrir un événement > **Historique sync**
3. Identifier l'erreur récurrente

**Solutions courantes :**
- 401 Unauthorized → Réinitialiser le token Outlook de l'utilisateur
- 404 Not Found → Problème microsoft_id, supprimer/recréer l'événement
- Timeout → Vérifier la connexion réseau

### Récurrences jusqu'en 9992

**Diagnostic :**
1. Consulter **Calendrier > Sync Outlook > Futur extrême**
2. Identifier les récurrences annuelles sans fin

**Solution :**
1. Supprimer l'événement dans Outlook
2. Le recréer avec date de fin (ex: 10 ans)
3. Ou nettoyage SQL :
```sql
DELETE FROM calendar_event WHERE EXTRACT(YEAR FROM stop) > 2030;
```

---

## Guide de test

Pour tester le module dans un environnement de test, consultez le fichier **TESTING.md** qui contient :

- Configuration complète d'un environnement Azure AD de test
- Création de comptes Microsoft gratuits
- Import du fichier `test_events.ics` (30 événements de test)
- 5 scénarios de test détaillés
- FAQ complète sur la configuration Azure

**Fichier de test fourni :** `tests/test_events.ics` avec 30 événements couvrant tous les cas d'usage.

---

## Support

### Documentation

- **Guide de test complet** : `TESTING.md`
- **Issue technique pour Odoo** : `ISSUE_ODOO.md`
- **Synthèse client** : `SYNTHESE_CLIENT.md`

### Ressources externes

- **Documentation Odoo** : https://www.odoo.com/documentation/17.0/
- **Microsoft Graph API** : https://docs.microsoft.com/graph
- **Issue GitHub #148011** : https://github.com/odoo/odoo/issues/148011

### Contact

Pour toute question ou problème :
- Consulter la documentation ci-dessus
- Ouvrir une issue sur GitHub

---

## Licence

LGPL-3

## Auteur

**Nicolas JEUDY - ALUSAGE SAS**

Contributeurs : Sudokeys

© 2025

## Changelog

### Version 17.0.1.0.0 (2025-11-27)

- Version initiale
- Logging complet des opérations de sync
- Rapports markdown automatiques (cron)
- Assistant d'analyse interactif (5 types d'analyses)
- Détection d'anomalies (bloqués, année 9992)
- Configuration avancée des limites
- Dashboard de monitoring
- Scripts de production (Python + Bash)
- Fichier de test .ics avec 30 événements
