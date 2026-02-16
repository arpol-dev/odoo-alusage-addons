# Issue: Problèmes critiques de synchronisation Outlook Calendar dans Odoo 17.0 Enterprise

**Version:** Odoo 17.0 Enterprise
**Module:** microsoft_calendar
**Environnement:** Production avec plusieurs clients
**Date:** 2025-11-27

---

## 📋 Résumé exécutif

Nous rencontrons des problèmes majeurs de synchronisation entre Odoo 17.0 Enterprise et Outlook Calendar affectant plusieurs clients en production. Ces problèmes impactent la fiabilité de la synchronisation et génèrent des données anormales dans la base de données.

---

## 🔴 Problème 1: Récurrences créées jusqu'en l'année 9992

### Description
Lors de la synchronisation d'événements récurrents depuis Outlook vers Odoo, certains événements sont créés avec des dates allant jusqu'à l'année 9992.

### Code source concerné
Fichier: `odoo/addons/microsoft_calendar/models/microsoft_sync.py`

```python
MAX_RECURRENT_EVENT = 720  # Ligne 23
```

Fichier: `odoo/addons/microsoft_calendar/models/calendar.py`

```python
# Lignes 598-602
if recurrence.end_type == 'count':
    rule_range['numberOfOccurrences'] = min(recurrence.count, MAX_RECURRENT_EVENT)
    rule_range['type'] = 'numbered'
elif recurrence.end_type == 'forever':
    rule_range['numberOfOccurrences'] = MAX_RECURRENT_EVENT
    rule_range['type'] = 'numbered'
```

### Analyse
1. Odoo limite les récurrences à **720 occurrences** (`MAX_RECURRENT_EVENT`)
2. Pour les récurrences de type `forever` (sans fin), Odoo force `numberOfOccurrences = 720`
3. Outlook génère ces 720 occurrences qui peuvent s'étendre très loin dans le futur
4. Une récurrence quotidienne sur 720 jours = ~2 ans, mais une récurrence annuelle sur 720 ans = année 9992 !

### Reproduction
1. Créer une récurrence annuelle dans Outlook (ex: anniversaire, congé annuel)
2. Marquer la récurrence comme "sans fin" (forever)
3. Synchroniser avec Odoo
4. Observer les événements créés avec des dates en 9992

### Impact
- Base de données polluée avec des milliers d'événements futurs inutiles
- Performances dégradées lors des requêtes sur calendar.event
- Confusion pour les utilisateurs
- Impossibilité de gérer correctement ces événements

### Solution proposée
```python
# Ajouter une limite temporelle en plus de la limite de comptage
MAX_RECURRENT_EVENT = 720
MAX_RECURRENT_YEARS = 5  # Nouvelle constante

# Dans calendar.py, ligne 598-602
if recurrence.end_type == 'count':
    rule_range['numberOfOccurrences'] = min(recurrence.count, MAX_RECURRENT_EVENT)
    rule_range['type'] = 'numbered'
elif recurrence.end_type == 'forever':
    # Calculer le nombre max d'occurrences selon l'intervalle
    max_occurrences = MAX_RECURRENT_EVENT
    if recurrence.rrule_type == 'yearly':
        max_occurrences = min(MAX_RECURRENT_EVENT, MAX_RECURRENT_YEARS)
    elif recurrence.rrule_type == 'monthly':
        max_occurrences = min(MAX_RECURRENT_EVENT, MAX_RECURRENT_YEARS * 12)

    rule_range['numberOfOccurrences'] = max_occurrences
    rule_range['type'] = 'numbered'
```

---

## 🔴 Problème 2: 256 événements bloqués en `need_sync_m` (congés 2025)

### Description
Nous avons 256 événements de congés pour 2025 qui restent bloqués avec `need_sync_m=True`. Aucune erreur n'est retournée, mais la synchronisation ne se fait jamais.

### Code source concerné
Fichier: `odoo/addons/microsoft_calendar/models/microsoft_sync.py`

```python
# Lignes 80-98: La méthode write qui gère need_sync_m
def write(self, vals):
    fields_to_sync = [x for x in vals if x in self._get_microsoft_synced_fields()]
    if fields_to_sync and 'need_sync_m' not in vals and self.env.user._get_microsoft_sync_status() == "sync_active":
        vals['need_sync_m'] = True

    result = super().write(vals)

    if self.env.user._get_microsoft_sync_status() != "sync_paused":
        for record in self:
            if record.need_sync_m and record.ms_organizer_event_id:
                if not vals.get('active', True):
                    record._microsoft_delete(record._get_organizer(), record.ms_organizer_event_id, timeout=3)
                elif fields_to_sync:
                    values = record._microsoft_values(fields_to_sync)
                    if not values:
                        continue
                    record._microsoft_patch(record._get_organizer(), record.ms_organizer_event_id, values, timeout=3)

    return result
```

### Hypothèses sur les causes

#### Hypothèse 1: Problème avec le décorateur `@after_commit`
Les méthodes `_microsoft_patch`, `_microsoft_insert` et `_microsoft_delete` utilisent le décorateur `@after_commit` (ligne 29-51). Si une exception se produit dans le callback post-commit, elle est loggée mais `need_sync_m` n'est pas réinitialisé.

```python
@after_commit
def _microsoft_patch(self, user_id, event_id, values, timeout=TIMEOUT):
    # ...
    try:
        res = microsoft_service.patch(event_id, values, token=token, timeout=timeout)
        self.with_context(dont_notify=True).write({
            'need_sync_m': not res,  # Si res=False, need_sync_m reste True
        })
    except Exception as e:
        # Exception silencieuse, need_sync_m reste True
        _logger.warning("Could not sync record now: %s" % self)
```

#### Hypothèse 2: Token invalide ou expiré
Si le token Microsoft est expiré, l'API retourne une erreur 401 mais cette erreur est catchée et loggée sans remettre `need_sync_m` à False.

#### Hypothèse 3: Problème d'organisateur
D'après le [GitHub Issue #148011](https://github.com/odoo/odoo/issues/148011), si un utilisateur A crée un événement et invite l'utilisateur B:
- L'événement est synchronisé pour B avec le `microsoft_id` spécifique à B
- Odoo essaie de resynchroniser avec le token de A (organisateur) mais le `microsoft_id` de B
- L'API Microsoft retourne 404
- `need_sync_m` reste True indéfiniment

### Logs nécessaires pour diagnostiquer

**Actuellement, il n'y a AUCUN moyen de tracer ce qui se passe !**

Nous avons besoin de:
1. Logs détaillés pour chaque tentative de sync avec timestamps
2. Code réponse de l'API Microsoft
3. Token utilisé (user_id)
4. microsoft_id utilisé
5. Détection des timeouts
6. Rapport automatique des événements bloqués

### Requêtes SQL pour diagnostic en production

```sql
-- Compter les événements need_sync_m par utilisateur
SELECT
    ru.name,
    ru.login,
    COUNT(*) as count_need_sync
FROM calendar_event ce
JOIN calendar_event_res_partner_rel cepr ON cepr.calendar_event_id = ce.id
JOIN res_partner rp ON rp.id = cepr.res_partner_id
JOIN res_users ru ON ru.partner_id = rp.id
WHERE ce.need_sync_m = true
GROUP BY ru.id, ru.name, ru.login
ORDER BY count_need_sync DESC;

-- Identifier les événements bloqués depuis plus de 7 jours
SELECT
    ce.id,
    ce.name,
    ce.start,
    ce.microsoft_id,
    ru.name as user_name,
    ce.write_date,
    NOW() - ce.write_date as stuck_duration
FROM calendar_event ce
JOIN calendar_event_res_partner_rel cepr ON cepr.calendar_event_id = ce.id
JOIN res_partner rp ON rp.id = cepr.res_partner_id
JOIN res_users ru ON ru.partner_id = rp.id
WHERE ce.need_sync_m = true
AND ce.write_date < NOW() - INTERVAL '7 days'
ORDER BY ce.write_date;

-- Chercher les événements avec dates extrêmes
SELECT
    id,
    name,
    start,
    stop,
    EXTRACT(YEAR FROM stop) as year_stop
FROM calendar_event
WHERE EXTRACT(YEAR FROM stop) > 2030
ORDER BY stop DESC
LIMIT 100;
```

### Solution proposée
Voir le module `outlook_sync_analyzer` développé ci-dessous.

---

## 🔴 Problème 3: Absence de traçabilité des synchronisations

### Description
Il n'existe **AUCUN système de logging** pour tracer les opérations de synchronisation. Quand un problème survient:
- Aucun log détaillé
- Aucun rapport automatique
- Aucune visibilité sur les timeouts
- Aucune alerte sur les anomalies

### Code actuel
```python
# microsoft_sync.py, lignes 40-50
@self.env.cr.postcommit.add
def called_after():
    db_registry = registry(dbname)
    with db_registry.cursor() as cr:
        env = api.Environment(cr, uid, context)
        try:
            func(self.with_env(env), *args, **kwargs)
        except Exception as e:
            _logger.warning("Could not sync record now: %s" % self)
            _logger.exception(e)
            # FIN ! Aucune trace persistante, aucun rapport
```

### Informations manquantes
1. Quel utilisateur a déclenché la sync ?
2. Combien d'événements ont été traités ?
3. Combien ont réussi/échoué ?
4. Quel est le code réponse de l'API Microsoft ?
5. Y a-t-il eu un timeout ?
6. Combien de temps a pris l'opération ?
7. Historique des tentatives pour un événement donné

---

## 🔴 Problème 4: Récupération illimitée d'anciens événements

### Description
Lors de la synchronisation Outlook → Odoo, le système récupère des événements très anciens, potentiellement depuis des années.

### Code source
Fichier: `odoo/addons/microsoft_calendar/utils/microsoft_calendar.py`

```python
# Lignes 67-73
# Par défaut, récupère 1 an dans le passé et 2 ans dans le futur
day_range = int(self.microsoft_service.env['ir.config_parameter'].sudo().get_param(
    'microsoft_calendar.sync.range_days', default=365))
params = {
    'startDateTime': fields.Datetime.subtract(fields.Datetime.now(), days=day_range).strftime("%Y-%m-%dT00:00:00Z"),
    'endDateTime': fields.Datetime.add(fields.Datetime.now(), days=day_range * 2).strftime("%Y-%m-%dT00:00:00Z"),
}
```

Fichier: `odoo/addons/microsoft_calendar/models/calendar.py`

```python
# Lignes 276-291
def _get_microsoft_sync_domain(self):
    ICP = self.env['ir.config_parameter'].sudo()
    day_range = int(ICP.get_param('microsoft_calendar.sync.range_days', default=365))
    lower_bound = fields.Datetime.subtract(fields.Datetime.now(), days=day_range)
    upper_bound = fields.Datetime.add(fields.Datetime.now(), days=day_range)

    # ...
    domain = [
        ('partner_ids.user_ids', 'in', self.env.user.id),
        ('stop', '>', lower_bound),
        ('start', '<', upper_bound),
        # ...
    ]
```

### Problèmes
1. **Par défaut 365 jours**: récupère 1 an d'historique à chaque sync
2. **Pas de limite configurable côté utilisateur**: seul un admin système peut modifier le paramètre
3. **Synchronisation bidirectionnelle problématique**:
   - Outlook → Odoo récupère de vieux événements
   - Ces événements déclenchent des updates Odoo → Outlook
   - Génère du spam de notifications pour des événements passés

### Configuration actuelle

Le paramètre `microsoft_calendar.sync.range_days` existe mais:
- N'est pas documenté
- N'est pas accessible via l'interface
- Sa valeur par défaut (365 jours) est trop large pour beaucoup de cas

### Impact observé
- Synchronisation lente lors de la première sync (milliers d'événements)
- Notifications Outlook pour des événements passés
- Pollution de la base avec des événements obsolètes
- Consommation inutile d'API Microsoft

### Solutions proposées

#### 1. Paramètre accessible dans l'interface
```xml
<!-- Dans res_config_settings -->
<field name="microsoft_calendar_sync_range_days"/>
<field name="microsoft_calendar_sync_lower_bound_range"/>
```

#### 2. Valeur par défaut plus raisonnable
- **30 jours** dans le passé au lieu de 365
- **365 jours** dans le futur (conservé)

#### 3. Paramètre de première synchronisation
```python
# Nouveau paramètre système
microsoft_calendar.sync.first_synchronization_date

# Modifier _get_microsoft_sync_domain pour l'utiliser
first_sync_date = ICP.get_param('microsoft_calendar.sync.first_synchronization_date')
if first_sync_date:
    domain = expression.AND([domain, [('create_date', '>=', first_sync_date)]])
```

---

## 🔴 Problème 5: Pas de rapport par compte utilisateur

### Description
Il n'existe aucun moyen simple pour:
1. Voir combien d'événements sont synchronisés par utilisateur
2. Identifier les utilisateurs avec des problèmes de sync
3. Obtenir un rapport clair de l'état de synchronisation
4. Comparer les événements synchronisés vs non synchronisés

### Besoins
- Dashboard par utilisateur
- Rapport exportable en markdown
- Statistiques de synchronisation
- Identification rapide des problèmes

---

## 💡 Solution proposée: Module `outlook_sync_analyzer`

J'ai développé un module complet pour résoudre tous ces problèmes. Le module est disponible dans le répertoire du projet.

### Fonctionnalités

#### 1. Logging détaillé
- Enregistrement de toutes les opérations de sync (insert, patch, delete, sync M2O, O2M)
- Timestamps, durées, codes de réponse API
- Comptage automatique des `need_sync_m` avant/après
- Détection des exceptions et timeouts

#### 2. Rapports markdown automatiques
- Génération automatique à chaque synchronisation
- Sauvegarde sur le serveur dans un chemin configurable
- Format markdown lisible et exploitable
- Résumé des statistiques et anomalies

#### 3. Détection d'anomalies
- Récurrences avec dates futures extrêmes (> année configurable)
- Événements anciens synchronisés
- Événements bloqués en `need_sync_m` > 7 jours
- Événements sans email
- Doublons

#### 4. Analyse et rapports
- Rapport par utilisateur
- Rapport global pour tous les utilisateurs
- Vue des événements bloqués
- Vue des événements futurs extrêmes
- Historique de sync par événement

#### 5. Configuration interface
- Activation/désactivation du logging
- Configuration des limites de dates
- Configuration du chemin des rapports
- Accès aux paramètres système microsoft_calendar

### Installation

```bash
# Le module est déjà dans votre addons-path
# Dans Odoo:
# 1. Apps > Update Apps List
# 2. Chercher "Outlook Sync Analyzer"
# 3. Installer
```

### Configuration

1. Aller dans **Paramètres > Outlook Sync Analyzer**
2. Activer le logging détaillé
3. Activer la génération de rapports markdown
4. Configurer le chemin des rapports (ex: `/var/log/odoo/outlook_sync`)
5. Ajuster les limites:
   - Plage de sync: 30 jours (au lieu de 365)
   - Borne inférieure: 30 jours
   - Année future max: 2030
   - Limite événements anciens: 365 jours

### Utilisation

#### Menu "Sync Outlook"
- **Logs de synchronisation**: Voir tous les logs détaillés
- **Rapports**: Consulter les rapports markdown générés
- **Événements à synchroniser**: Liste des need_sync_m
- **Événements bloqués**: Liste des événements stuck > 7 jours
- **Futur extrême**: Liste des événements avec dates anormales

#### Actions sur les événements
- **Historique sync**: Voir l'historique de synchronisation d'un événement
- **Forcer resync**: Marquer manuellement pour resynchronisation

#### Rapports utilisateur
- Aller dans **Paramètres > Utilisateurs**
- Sélectionner un utilisateur
- Bouton **Voir rapport Outlook**

#### Rapport global
- **Paramètres > Outlook Sync Analyzer**
- Bouton **Générer rapport global**

### Structure des rapports markdown

```markdown
# Rapport de synchronisation Outlook

**Date:** 2025-11-27 10:30:00
**Utilisateur:** John Doe (john.doe@example.com)
**Opération:** Microsoft → Odoo
**Statut:** Succès

## Statistiques

- Durée: 1234ms
- Événements traités: 50
- Créés: 5
- Mis à jour: 40
- Supprimés: 3
- Erreurs: 2

## Need Sync Status

- Avant: 260
- Après: 256
- Delta: -4

## ⚠️ Anomalie détectée

**Type:** Récurrence future extrême

**Détails:**
```
Événements avec dates > 2030:
- Anniversaire Pierre: 2050-03-15
- Congé annuel: 9992-12-31
```

## ❌ Erreur

```
Event ID AAMkAGI2T... returned 404: Resource not found
User token: user.a@company.com
Microsoft ID: AAMkAGI2T... (from user.b@company.com)
```
```

---

## 📊 Requêtes SQL utiles pour diagnostic

```sql
-- 1. Vue d'ensemble par utilisateur
SELECT
    ru.name,
    ru.login,
    COUNT(*) FILTER (WHERE ce.microsoft_id IS NOT NULL) as synced,
    COUNT(*) FILTER (WHERE ce.need_sync_m = true) as need_sync,
    COUNT(*) FILTER (WHERE ce.need_sync_m = true AND ce.write_date < NOW() - INTERVAL '7 days') as stuck,
    COUNT(*) as total
FROM res_users ru
JOIN res_partner rp ON rp.id = ru.partner_id
JOIN calendar_event_res_partner_rel cepr ON cepr.res_partner_id = rp.id
JOIN calendar_event ce ON ce.id = cepr.calendar_event_id
WHERE ru.microsoft_calendar_rtoken IS NOT NULL
GROUP BY ru.id, ru.name, ru.login;

-- 2. Événements bloqués avec détails
SELECT
    ce.id,
    ce.name,
    ce.start,
    ce.stop,
    ce.microsoft_id,
    ru.name as user_name,
    ru.login,
    ce.write_date,
    EXTRACT(DAY FROM NOW() - ce.write_date) as days_stuck
FROM calendar_event ce
JOIN calendar_event_res_partner_rel cepr ON cepr.calendar_event_id = ce.id
JOIN res_partner rp ON rp.id = cepr.res_partner_id
JOIN res_users ru ON ru.partner_id = rp.id
WHERE ce.need_sync_m = true
AND ce.write_date < NOW() - INTERVAL '7 days'
ORDER BY days_stuck DESC;

-- 3. Détection récurrences anormales
SELECT
    ce.id,
    ce.name,
    ce.start,
    ce.stop,
    EXTRACT(YEAR FROM ce.stop) as year_stop,
    ce.recurrence_id,
    cr.rrule
FROM calendar_event ce
LEFT JOIN calendar_recurrence cr ON cr.id = ce.recurrence_id
WHERE EXTRACT(YEAR FROM ce.stop) > 2030
ORDER BY ce.stop DESC;

-- 4. Statistiques de synchronisation par date
SELECT
    DATE(ce.write_date) as date,
    COUNT(*) FILTER (WHERE ce.microsoft_id IS NOT NULL) as synced_events,
    COUNT(*) FILTER (WHERE ce.need_sync_m = true) as need_sync_events
FROM calendar_event ce
WHERE ce.write_date >= NOW() - INTERVAL '30 days'
GROUP BY DATE(ce.write_date)
ORDER BY date DESC;

-- 5. Identifier les événements orphelins (microsoft_id sans iCalUId)
SELECT
    id,
    name,
    microsoft_id,
    CASE
        WHEN microsoft_id LIKE '%:%' THEN split_part(microsoft_id, ':', 1)
        ELSE microsoft_id
    END as organizer_id,
    CASE
        WHEN microsoft_id LIKE '%:%' THEN split_part(microsoft_id, ':', 2)
        ELSE NULL
    END as universal_id
FROM calendar_event
WHERE microsoft_id IS NOT NULL
AND (microsoft_id NOT LIKE '%:%' OR split_part(microsoft_id, ':', 2) = '');
```

---

## 🎯 Actions recommandées

### Court terme (urgent)

1. **Installer le module outlook_sync_analyzer** dans tous les environnements de production
2. **Activer le logging** pour capturer les problèmes
3. **Exécuter les requêtes SQL** pour identifier l'ampleur des problèmes
4. **Générer les rapports** par utilisateur et analyser les événements bloqués
5. **Configurer les limites**:
   - `microsoft_calendar.sync.range_days = 30`
   - `microsoft_calendar.sync.lower_bound_range = 30`
   - `outlook_sync_analyzer.future_year_limit = 2030`

### Moyen terme

1. **Nettoyer les événements anormaux**:
```sql
-- Sauvegarder d'abord !
-- Supprimer les événements avec dates > 2030
DELETE FROM calendar_event WHERE EXTRACT(YEAR FROM stop) > 2030;
```

2. **Réinitialiser les événements bloqués**:
```sql
-- Forcer resync pour les événements bloqués > 30 jours
UPDATE calendar_event
SET need_sync_m = false
WHERE need_sync_m = true
AND write_date < NOW() - INTERVAL '30 days';
```

3. **Configurer la date de première sync**:
```python
# Via Odoo shell
self.env['ir.config_parameter'].sudo().set_param(
    'microsoft_calendar.sync.first_synchronization_date',
    '2024-01-01 00:00:00'
)
```

### Long terme (à soumettre à Odoo)

1. **Corriger MAX_RECURRENT_EVENT** pour les récurrences annuelles
2. **Améliorer la gestion d'erreurs** dans `@after_commit`
3. **Ajouter un système de retry** pour les événements need_sync_m
4. **Résoudre le problème du microsoft_id** multi-utilisateurs (Issue #148011)
5. **Exposer les paramètres de sync** dans l'interface Settings
6. **Ajouter un logging natif** dans le core microsoft_calendar

---

## 📎 Liens de référence

### Issues GitHub Odoo
- [Issue #148011: Events synchronized from Outlook to Odoo by someone else than the organizer can no longer be synchronized back to Outlook](https://github.com/odoo/odoo/issues/148011)

### Documentation Odoo
- [Outlook Calendar synchronization — Odoo 17.0](https://www.odoo.com/documentation/17.0/applications/productivity/calendar/outlook.html)
- [Outlook Calendar synchronization — Odoo 18.0](https://www.odoo.com/documentation/18.0/applications/productivity/calendar/outlook.html)

### Forum Odoo
- [Outlook Calendar sync to microsoft](https://www.odoo.com/forum/help-1/outlook-calendar-sync-to-microsoft-202260)
- [Outlook / Odoo calendar integration issue](https://www.odoo.com/forum/help-1/outlook-odoo-calendar-integration-issue-262541)
- [Outlook sync is sending old meeting requests in bulk](https://www.odoo.com/forum/crm-2/outlook-sync-is-sending-old-meeting-requests-in-bulk-205358)

---

## 📧 Contact

Pour toute question ou information complémentaire, me contacter via le support Odoo Enterprise ou créer une issue sur le repository GitHub approprié.

**Modules développés:**
- `outlook_sync_analyzer`: Module complet de traçage et analyse des synchronisations Outlook

**Fichiers clés à examiner:**
- `/home/njeudy/dev/doc_technique/Odoo/odoo/odoo-17.0/addons/microsoft_calendar/models/microsoft_sync.py`
- `/home/njeudy/dev/doc_technique/Odoo/odoo/odoo-17.0/addons/microsoft_calendar/models/calendar.py`
- `/home/njeudy/dev/doc_technique/Odoo/odoo/odoo-17.0/addons/microsoft_calendar/utils/microsoft_calendar.py`
