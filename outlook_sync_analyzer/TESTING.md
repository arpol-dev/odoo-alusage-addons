# Guide de test - Outlook Sync Analyzer

Guide complet pour configurer un environnement de test et valider le fonctionnement du module.

---

## 📑 Table des matières

- [Prérequis](#prérequis)
- [Configuration Azure AD](#configuration-azure-ad)
- [Configuration Odoo](#configuration-odoo)
- [Import du fichier de test](#import-du-fichier-de-test)
- [Scénarios de test](#scénarios-de-test)
- [Validation](#validation)
- [FAQ](#faq)
- [Dépannage Azure](#dépannage-azure)

---

## Prérequis

### Ce qu'il vous faut

| Prérequis | Nécessaire | Coût | Où l'obtenir |
|-----------|------------|------|--------------|
| **Compte Microsoft** | ✅ OUI | **GRATUIT** | https://outlook.live.com |
| **Office 365** | ❌ NON | - | Pas besoin |
| **Domaine** | ❌ NON | - | Pas besoin pour localhost |
| **HTTPS** | ❌ NON | - | HTTP localhost suffit |
| **Odoo 17.0** | ✅ OUI | Selon licence | Votre installation |

### Compte Microsoft GRATUIT

**Vous n'avez PAS besoin d'Office 365 !**

Un compte **Outlook.com gratuit** suffit complètement :
- ✅ 100% GRATUIT
- ✅ Calendrier Outlook inclus
- ✅ API Microsoft Graph accessible
- ✅ Parfait pour les tests

**Créer un compte :**
1. Aller sur https://outlook.live.com
2. Cliquer "Créer un compte gratuit"
3. Choisir une adresse : `votretest@outlook.com` ou `votretest@hotmail.com`
4. C'est tout !

**Combien de comptes ?**

Créez **2-3 comptes** pour tester tous les scénarios :
1. **Compte principal** (organisateur) : `test.odoo.user1@outlook.com`
2. **Compte participant 1** : `test.odoo.user2@outlook.com`
3. **Compte participant 2** : `test.odoo.user3@outlook.com`

### HTTPS et domaine

**Pour les tests :** ❌ **PAS BESOIN**

Microsoft autorise explicitement `http://localhost` pour le développement.

**Configuration test (localhost) :**
```
Odoo: http://localhost:8069
Azure AD Redirect: http://localhost:8069/microsoft_account/authentication
HTTPS: Non requis
Domaine: Non requis
Coût: 0€
```

**Pour la production :** ✅ HTTPS obligatoire

---

## Configuration Azure AD

### Étape 1 : Créer l'application Azure AD

**URL d'accès :**
```
https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade
```

Se connecter avec votre compte Outlook.com de test.

### Étape 2 : Nouvelle inscription

Cliquer sur **"+ New registration"** (Nouvelle inscription)

### Étape 3 : Configuration de l'application

**Name (Nom) :**
```
Odoo Outlook Sync Test
```

**Supported account types (Types de comptes pris en charge) :**

⚠️ **IMPORTANT : Choisir la TROISIÈME option !**

```
✅ Accounts in any organizational directory (Any Azure AD directory - Multitenant)
   and personal Microsoft accounts (e.g. Skype, Xbox)
```

**Pourquoi ?** C'est la seule option qui accepte les comptes personnels Outlook.com !

**Redirect URI :**
```
Platform: Web
URI: http://localhost:8069/microsoft_account/authentication
```

Cliquer sur **"Register"**

### Étape 4 : Récupérer le Client ID

Dans la page **"Overview"** de votre application :

Copier **"Application (client) ID"** :
```
Example: 12345678-1234-1234-1234-123456789abc
```

### Étape 5 : Créer le Client Secret

1. Dans le menu de gauche, aller sur **"Certificates & secrets"**
2. Cliquer sur **"+ New client secret"**
3. Description : `Odoo Test Secret`
4. Expires : **24 months**
5. Cliquer sur **"Add"**
6. **⚠️ COPIER LA VALUE IMMÉDIATEMENT** (elle ne s'affichera plus !)
   ```
   Example: abc~XYZ123-_defGHI456...
   ```

### Étape 6 : Configurer les permissions

1. Dans le menu de gauche, aller sur **"API permissions"**
2. Cliquer sur **"+ Add a permission"**
3. Sélectionner **"Microsoft Graph"**
4. Sélectionner **"Delegated permissions"**

#### Permissions à ajouter

| Permission | Catégorie | Obligatoire | Où la trouver |
|------------|-----------|-------------|---------------|
| **Calendars.ReadWrite** | Calendars | ✅ OUI | Delegated permissions > Calendars > Calendars.ReadWrite |
| **User.Read** | User | ✅ OUI | Delegated permissions > User > User.Read (souvent déjà là) |
| **email** | OpenID | Recommandé | Delegated permissions > OpenId permissions > email |
| **openid** | OpenID | Recommandé | Delegated permissions > OpenId permissions > openid |
| **profile** | OpenID | Recommandé | Delegated permissions > OpenId permissions > profile |

**Astuce :** Utilisez la barre de recherche "Select permissions" et tapez directement le nom.

5. Cliquer sur **"Add permissions"**

#### Permission offline_access

⚠️ **IMPORTANT :** Ne cherchez PAS `offline_access` dans la liste Azure AD !

Cette permission est **automatiquement demandée** par Odoo lors de l'authentification OAuth2. Vous ne devez **PAS** l'ajouter manuellement.

### Étape 7 : Récapitulatif Azure AD

Vous devriez maintenant avoir :

```
✅ Application créée : "Odoo Outlook Sync Test"
✅ Supported accounts : Multitenant and personal accounts
✅ Redirect URI : http://localhost:8069/microsoft_account/authentication
✅ Client ID copié : 12345678-1234-...
✅ Client Secret copié : abc~XYZ123...
✅ Permissions ajoutées : 5 permissions (Calendars.ReadWrite, User.Read, email, openid, profile)
```

---

## Configuration Odoo

### Prérequis Odoo

```bash
# 1. Installer Odoo 17.0 Enterprise (si ce n'est pas déjà fait)
# 2. Installer le module microsoft_calendar (natif Odoo)
# 3. Installer le module outlook_sync_analyzer (ce module)
```

### Étape 1 : Lancer Odoo en local

```bash
# Lancer Odoo sur localhost
odoo-bin -d test_outlook -c odoo.conf

# Odoo sera accessible sur:
http://localhost:8069

# Se connecter avec:
# Email: admin
# Password: admin (ou votre mot de passe)
```

### Étape 2 : Configurer les identifiants Microsoft

**Paramètres > Technique > Paramètres système**

Créer/Modifier ces paramètres :

| Clé | Valeur |
|-----|--------|
| `microsoft_calendar_client_id` | Votre Application (client) ID |
| `microsoft_calendar_client_secret` | Votre Client Secret Value |

**Exemple :**
```
microsoft_calendar_client_id = 12345678-1234-1234-1234-123456789abc
microsoft_calendar_client_secret = abc~XYZ123-_defGHI456...
```

### Étape 3 : Activer le module de logging

**Paramètres > Outlook Sync Analyzer**

- ✅ **Activer le logging détaillé**
- ✅ **Générer des rapports markdown**
- **Chemin des rapports** : `/tmp/outlook_sync_reports` (pour les tests)

**Créer le répertoire :**
```bash
mkdir -p /tmp/outlook_sync_reports
chmod 777 /tmp/outlook_sync_reports
```

### Étape 4 : Configurer les limites (optionnel)

**Paramètres > Technique > Paramètres système**

Pour tester le filtrage des anciens événements :

| Clé | Valeur | Description |
|-----|--------|-------------|
| `microsoft_calendar.sync.range_days` | `365` | Par défaut (ou `30` pour limiter) |
| `microsoft_calendar.sync.lower_bound_range` | `30` | Évite updates d'événements anciens |

### Étape 5 : Connecter Outlook

1. **Calendrier** (Calendar app)
2. Cliquer sur **"Sync with Outlook"** ou **"Synchroniser avec Outlook"**
3. Vous serez redirigé vers Microsoft
4. Se connecter avec votre compte test : `test.user1@outlook.com`
5. Accepter les permissions demandées
6. Vous serez redirigé vers Odoo → ✅ **Connexion réussie !**

---

## Import du fichier de test

### Fichier test_events.ics

Le module fournit un fichier `tests/test_events.ics` contenant **30 événements de test** couvrant tous les cas d'usage :

- Événements simples, multi-participants, all-day
- Événements anciens (>1 an, >2 ans)
- Récurrences (daily, weekly, monthly, yearly)
- **TEST-011 : Bug année 9992** (récurrence annuelle infinie)
- Caractères spéciaux, emojis, descriptions longues
- Conflits horaires, événements privés/publics

### Méthode 1 : Via Outlook Web (recommandé)

1. **Se connecter à Outlook Web**
   ```
   https://outlook.live.com
   ```
   Se connecter avec `test.user1@outlook.com`

2. **Aller dans le Calendrier**
   - Cliquer sur l'icône Calendrier (📅) en bas à gauche

3. **Importer le fichier**
   - Cliquer sur **"Ajouter un calendrier"** (ou "Add calendar")
   - Sélectionner **"Télécharger à partir d'un fichier"** (ou "Upload from file")
   - Cliquer sur **"Parcourir"** et sélectionner `test_events.ics`
   - Choisir **"Importer dans le calendrier principal"**
   - Cliquer sur **"Importer"**

4. **Vérifier l'importation**
   - Les 30 événements devraient apparaître dans votre calendrier
   - Chercher les événements avec le préfixe `TEST-XXX`

### Méthode 2 : Double-clic (le plus simple)

1. Télécharger le fichier `test_events.ics` sur votre ordinateur
2. **Double-cliquer** sur le fichier
3. Votre application calendrier par défaut s'ouvre
4. Confirmer l'importation

### Liste des 30 événements de test

| ID | Nom | Type | Cas de test |
|----|-----|------|-------------|
| 001 | Réunion simple 1h | Simple | Événement standard |
| 002 | Réunion multi-participants | Multi-users | Issue #148011 |
| 003 | Événement toute la journée | All-day | DATE vs DATETIME |
| 004 | Journée de formation | Longue durée | 9 heures |
| 005 | Événement ancien (>1 an) | Ancien | Limite 365 jours |
| 006 | Événement très ancien (2 ans) | Très ancien | Ne devrait PAS sync |
| 007 | Récurrence quotidienne | DAILY | COUNT=5 |
| 008 | Récurrence hebdomadaire | WEEKLY | COUNT=4 |
| 009 | Récurrence mensuelle | MONTHLY | UNTIL |
| 010 | Récurrence annuelle SAFE | YEARLY | COUNT=5 ✅ |
| **011** | **⚠️ Récurrence annuelle INFINIE** | **YEARLY** | **BUG 9992 ❌** |
| 012 | Événement multi-jours | All-day | 3 jours |
| 013 | Événement avec rappel | Alarme | VALARM |
| 014 | Événement annulé | Cancelled | STATUS |
| 015 | Événement provisoire | Tentative | STATUS |
| 016 | Événement privé | Private | CLASS |
| 017 | Conférence publique | Public | CLASS |
| 018 | Récurrence complexe | WEEKLY | BYDAY multiple |
| 019 | Récurrence avec exception | EXDATE | Exclusion |
| 020 | Futur lointain (2026) | Futur | >1 an futur |
| 021 | Caractères spéciaux 🎉 | Unicode | Emojis |
| 022 | Description longue | Texte | >500 chars |
| 023 | Sans lieu | Optionnel | Pas de LOCATION |
| 024 | Minimal | Minimal | Champs minimum |
| 025-027 | Réunions back-to-back | Consécutif | 3 événements |
| 028-029 | Chevauchements | Conflit | Double booking |
| 030 | Modifié plusieurs fois | SEQUENCE | Historique |

---

## Scénarios de test

### Test 1 : Synchronisation initiale complète

**Objectif :** Vérifier que tous les événements récents sont synchronisés

**Étapes :**
1. Importer `test_events.ics` dans Outlook (voir ci-dessus)
2. Dans Odoo : **Calendrier > Sync with Outlook**
3. Attendre la synchronisation (5-10 secondes)
4. Consulter les logs : **Calendrier > Sync Outlook > Logs de synchronisation**
5. Générer un rapport d'analyse : **Calendrier > Sync Outlook > Analyse > Analyse globale**

**Résultats attendus :**
- ✅ Événements TEST-001 à TEST-004 : Synchronisés
- ✅ TEST-007 à TEST-030 : Synchronisés
- ❓ TEST-005 (>1 an) : Selon `sync.range_days` (si 365 → oui, si 30 → non)
- ❌ TEST-006 (2 ans) : Pas synchronisé (trop ancien)
- ⚠️ **TEST-011 : PROBLÈME - Événements jusqu'en 9992 créés !**

**Vérification SQL :**
```sql
-- Voir tous les événements de test
SELECT id, name, start, stop, recurrency, EXTRACT(YEAR FROM stop) as year_stop
FROM calendar_event
WHERE name LIKE 'TEST-%'
ORDER BY name;

-- Chercher le bug année 9992
SELECT id, name, stop, EXTRACT(YEAR FROM stop) as year_stop
FROM calendar_event
WHERE name LIKE 'TEST-011%'
  AND EXTRACT(YEAR FROM stop) > 2030
ORDER BY stop DESC
LIMIT 10;
```

**Résultat attendu TEST-011 :**
```
Total occurrences : ~720
Année max : 9992
```

### Test 2 : Événements multi-participants (Issue #148011)

**Objectif :** Reproduire le bug des événements bloqués en need_sync_m

**Configuration requise :** 2 comptes Microsoft (test.user1 et test.user2)

**Étapes :**
1. Dans Outlook (compte test.user1), éditer l'événement TEST-002
2. Inviter `test.user2@outlook.com` comme participant
3. Se connecter avec test.user2 dans Outlook
4. Accepter l'invitation à TEST-002
5. Dans Odoo, configurer les deux comptes (test.user1 et test.user2)
6. Synchroniser les deux comptes
7. Vérifier les `microsoft_id` des deux événements

**Résultats attendus :**
- ⚠️ Possibilité d'événements en `need_sync_m=True` à cause de microsoft_id différent
- Test.user1 (organisateur) : `microsoft_id` commence par l'ID de user1
- Test.user2 (participant) : `microsoft_id` commence par l'ID de user2 (différent !)

**Vérification SQL :**
```sql
-- Chercher les événements TEST-002 avec microsoft_id différent
SELECT u.name as user, ce.name, ce.microsoft_id, ce.need_sync_m
FROM calendar_event ce
JOIN calendar_event_res_partner_rel cepr ON ce.id = cepr.calendar_event_id
JOIN res_partner p ON cepr.res_partner_id = p.id
JOIN res_users u ON p.id = u.partner_id
WHERE ce.name LIKE 'TEST-002%'
ORDER BY u.name;
```

**Diagnostic avec le module :**
- **Calendrier > Sync Outlook > Événements bloqués**
- Ouvrir TEST-002 > **Historique sync**
- Chercher les erreurs 404 Not Found

### Test 3 : Récurrences (problème année 9992)

**Objectif :** Comparer récurrence limitée vs infinie

**Comparaison :**

| Événement | RRULE | Résultat Odoo attendu |
|-----------|-------|----------------------|
| TEST-010 | YEARLY;COUNT=5 | ✅ 5 événements (2025-2029) |
| **TEST-011** | **YEARLY** (infini) | **❌ 720 événements (2025-9992)** |

**Vérification SQL :**
```sql
-- Compter les occurrences de TEST-010 (devrait être 5)
SELECT COUNT(*) as count_010
FROM calendar_event
WHERE name LIKE 'TEST-010%';

-- Compter les occurrences de TEST-011 (devrait être ~720 !)
SELECT COUNT(*) as total_occurrences,
       MIN(EXTRACT(YEAR FROM stop)) as min_year,
       MAX(EXTRACT(YEAR FROM stop)) as max_year
FROM calendar_event
WHERE name LIKE 'TEST-011%';
```

**Via l'interface :**
- **Calendrier > Sync Outlook > Futur extrême**
- Voir TEST-011 avec des occurrences jusqu'en 9992

### Test 4 : Génération automatique de rapport

**Objectif :** Vérifier que le cron génère des rapports markdown

**Étapes :**
1. Vérifier que la génération est activée :
   - **Paramètres > Outlook Sync Analyzer > ✅ Générer des rapports markdown**
2. Lancer manuellement le cron :
   ```python
   # Shell Odoo (odoo-bin shell -d test_outlook)
   env['res.users']._sync_all_microsoft_calendar()
   ```
3. Consulter le rapport généré :
   - **Calendrier > Sync Outlook > Rapports**
   - Ou fichier : `/tmp/outlook_sync_reports/sync_report_YYYY-MM-DD_HH-MM-SS.md`

**Résultats attendus :**
- ✅ Rapport markdown créé
- ✅ Section "Synthèse" avec statistiques avant/après
- ✅ Section "Détails par utilisateur"
- ✅ Section "Anomalies détectées" montre :
  - Événements futur extrême (TEST-011)
  - Événements bloqués (si Test 2 reproduit)

**Contenu du rapport :**
```markdown
# Rapport de synchronisation Outlook - Tâche planifiée

**Date d'exécution:** 2025-11-27 10:15:00
...

## ⚠️ Anomalies détectées

- **Événements futur extrême:** 720 événements
  - TEST-011: Récurrence annuelle INFINIE (max: 9992)

## 📋 Recommandations

- **720 événements avec dates extrêmes** : Nettoyer les récurrences anormales
```

### Test 5 : Assistant d'analyse interactif

**Objectif :** Utiliser le wizard pour détecter les problèmes

**Étapes :**
1. **Calendrier > Sync Outlook > Analyse de synchronisation**
2. Sélectionner **"Analyse globale"**
3. Laisser les paramètres par défaut :
   - Seuil jours bloqués : 7
   - Seuil année future : 2030
4. Cliquer **"Lancer l'analyse"**
5. Consulter les résultats (onglets "Résultats" et "Markdown")

**Sections attendues dans le rapport :**
- 📊 **Statistiques globales**
  - Total événements : ~30+ (avec les 720 occurrences de TEST-011)
  - Need sync : Variable
  - Événements futur extrême : ~720
  - Événements bloqués : 0-5

- 🔴 **Événements futur extrême**
  - TEST-011 avec occurrences jusqu'en 9992

- ⚠️ **Événements bloqués** (si Test 2 reproduit)
  - TEST-002 si microsoft_id différent

- 📅 **Distribution temporelle**
  - Événements par année

**Test des autres types d'analyses :**

2. **"Par utilisateur"** :
   - Voir la répartition par utilisateur (test.user1, test.user2 si configuré)

3. **"Événements bloqués"** :
   - Liste des événements en need_sync_m > 7 jours

4. **"Récurrences anormales"** :
   - Liste détaillée des 720 occurrences de TEST-011

5. **"Comparaison utilisateurs"** :
   - Top utilisateurs problématiques

---

## Validation

### Checklist de validation

- [ ] **30 événements** importés dans Outlook
- [ ] Synchronisation Outlook→Odoo effectuée sans erreur
- [ ] Rapport de synchronisation généré (cron)
- [ ] Événements récents (TEST-001 à TEST-004) présents dans Odoo
- [ ] Récurrences créées (TEST-007 à TEST-011)
- [ ] **BUG 9992 reproduit** : TEST-011 a créé ~720 événements jusqu'en 9992
- [ ] Événements anciens (TEST-005, TEST-006) filtrés selon `sync.range_days`
- [ ] Événements avec participants (TEST-002) synchronisés
- [ ] Événements all-day (TEST-003, TEST-012) correctement importés
- [ ] Caractères spéciaux (TEST-021) préservés
- [ ] Statuts (TEST-014 cancelled, TEST-015 tentative) respectés
- [ ] Assistant d'analyse fonctionne (5 types d'analyses)
- [ ] Logs de synchronisation visibles dans l'interface
- [ ] Rapports markdown sauvegardés sur le serveur

### SQL de validation complète

```sql
-- Vue d'ensemble des événements de test
SELECT
    name,
    start::date as date_debut,
    recurrency,
    need_sync_m,
    EXTRACT(YEAR FROM stop) as annee_fin,
    CASE
        WHEN EXTRACT(YEAR FROM stop) > 2030 THEN '🔴 ANOMALIE'
        ELSE '✅ OK'
    END as statut
FROM calendar_event
WHERE name LIKE 'TEST-%'
ORDER BY name;

-- Détecter les événements problématiques
SELECT
    'Année 9992' as probleme,
    COUNT(*) as count
FROM calendar_event
WHERE name LIKE 'TEST-%'
  AND EXTRACT(YEAR FROM stop) > 2030

UNION ALL

SELECT
    'Need sync bloqué' as probleme,
    COUNT(*) as count
FROM calendar_event
WHERE name LIKE 'TEST-%'
  AND need_sync_m = true
  AND write_date < NOW() - INTERVAL '7 days';
```

### Nettoyage après tests

**Supprimer tous les événements de test :**

**Depuis Odoo (SQL) :**
```sql
-- ATTENTION : Sauvegarde recommandée avant !
DELETE FROM calendar_event WHERE name LIKE 'TEST-%';
```

**Depuis Odoo (Python shell) :**
```python
# Shell Odoo
test_events = env['calendar.event'].search([('name', 'like', 'TEST-%')])
print(f"Suppression de {len(test_events)} événements de test")
test_events.unlink()
env.cr.commit()
```

**Depuis Outlook Web :**
1. Aller dans le calendrier
2. Chercher `TEST-`
3. Sélectionner tous les événements
4. Supprimer

---

## FAQ

### Q: Quel type de compte Microsoft me faut-il ?

**R: Un compte Microsoft GRATUIT suffit complètement !**

Vous avez plusieurs options :

**Option 1: Compte Outlook.com (RECOMMANDÉ pour les tests)**
- ✅ **100% GRATUIT**
- ✅ Pas besoin d'Office 365
- ✅ Calendrier Outlook inclus
- ✅ API Microsoft Graph accessible
- ✅ Parfait pour les tests

**Comment créer:**
1. Aller sur https://outlook.live.com
2. Cliquer "Créer un compte gratuit"
3. Choisir une adresse: `votretest@outlook.com` ou `votretest@hotmail.com`
4. C'est tout !

**Option 2: Compte Microsoft personnel**
- ✅ Gratuit
- ✅ Si vous avez déjà un compte Microsoft (Xbox, Skype, etc.)

**Option 3: Office 365 (PAS NÉCESSAIRE pour les tests)**
- ❌ Payant (abonnement)
- ⚠️ Utile seulement pour tester en environnement professionnel

### Q: Est-ce que j'ai besoin de HTTPS ?

**R: NON pour les tests en local, OUI pour la production**

**Pour les TESTS (environnement local) : ✅ HTTP suffit !**

Microsoft autorise `http://localhost` comme URL de redirection pour les tests.

**Configuration Azure AD pour les tests:**
```
Redirect URI: http://localhost:8069/microsoft_account/authentication
```

**Avantages:**
- ✅ Pas besoin de certificat SSL
- ✅ Pas besoin de domaine
- ✅ Fonctionne sur votre machine locale
- ✅ Parfait pour développement/test

**Pour la PRODUCTION : ❌ HTTPS OBLIGATOIRE !**

Microsoft refuse `http://` pour les comptes en production.

**Configuration Azure AD pour production:**
```
Redirect URI: https://votre-domaine.com/microsoft_account/authentication
```

### Q: localhost suffit pour tester ?

**R: OUI, parfaitement !**

**Configuration complète localhost:**

```bash
# 1. Lancer Odoo en local
odoo-bin -d outlook_sync_test -c odoo.conf

# 2. Odoo sera accessible sur:
http://localhost:8069

# 3. Dans Azure AD, configurer:
Redirect URI: http://localhost:8069/microsoft_account/authentication

# 4. Dans Odoo, aller sur:
http://localhost:8069/web
```

✅ **Ça marche !** Microsoft autorise explicitement `http://localhost` pour le développement.

### Q: Comment tester depuis une autre machine ?

**R: Utiliser ngrok (pour tests à distance)**

**ngrok** crée un tunnel HTTPS vers votre machine locale.

```bash
# 1. Installer ngrok
# Télécharger sur https://ngrok.com (gratuit)
# ou
sudo snap install ngrok

# 2. Lancer Odoo localement
odoo-bin -d outlook_sync_test

# 3. Créer le tunnel HTTPS
ngrok http 8069

# 4. ngrok affiche:
# Forwarding: https://abc123.ngrok.io -> http://localhost:8069

# 5. Dans Azure AD:
Redirect URI: https://abc123.ngrok.io/microsoft_account/authentication

# 6. Accéder à Odoo via:
https://abc123.ngrok.io
```

**✅ Avantages:**
- HTTPS automatique (certificat valide)
- Accessible de partout
- Gratuit pour les tests
- Parfait pour tester l'authentification Microsoft

**❌ Inconvénients:**
- URL change à chaque redémarrage (version gratuite)
- Nécessite de mettre à jour Azure AD à chaque fois
- Pas pour la production

### Q: Combien de comptes dois-je créer ?

**R: Minimum 2-3 comptes pour tester tous les scénarios**

1. **Compte principal** (organisateur): `test.odoo.user1@outlook.com`
2. **Compte participant 1**: `test.odoo.user2@outlook.com`
3. **Compte participant 2**: `test.odoo.user3@outlook.com`

**Pourquoi plusieurs comptes ?**
- Tester les événements multi-participants
- Reproduire le bug Issue #148011 (organisateur différent)
- Vérifier les permissions et synchronisations croisées

### Q: Puis-je utiliser mon vrai compte Outlook professionnel ?

**R: OUI mais PAS RECOMMANDÉ pour les tests !**

⚠️ **Risques:**
- Pollution de votre calendrier réel avec des événements de test
- Risque de supprimer/modifier des événements réels
- Collègues qui reçoivent des invitations de test

✅ **Recommandation:**
- Créer des comptes de test dédiés
- Garder votre compte professionnel pour la production

---

## Dépannage Azure

### Erreur: "AADSTS16000: does not exist in tenant"

**Erreur complète :**
```
interaction_required: AADSTS16000: User account from identity provider 'live.com'
does not exist in tenant 'Microsoft Services' and cannot access the application
```

**Cause :** Application configurée en "Single tenant" mais compte personnel utilisé

**Solution :** Recréer l'application avec "Multitenant and personal accounts"

**Étapes :**
1. Supprimer l'application actuelle dans Azure AD
2. Créer une nouvelle application
3. **Important :** Choisir **"Multitenant and personal accounts"** (3ème option)
4. Configurer le Redirect URI : `http://localhost:8069/microsoft_account/authentication`
5. Ajouter les permissions
6. Créer un nouveau Client Secret

### Erreur: "Je ne trouve pas offline_access"

**C'est NORMAL !**

La permission `offline_access` n'apparaît **PAS** dans la liste des permissions Azure AD.

**Pourquoi ?**

C'est une permission OpenID Connect qui est **automatiquement demandée** par Odoo lors de l'authentification OAuth2.

**Que faire ?**

Rien ! Ajoutez seulement :
1. ✅ Calendars.ReadWrite
2. ✅ User.Read
3. ✅ email, openid, profile (optionnel)

`offline_access` sera demandée automatiquement.

### Erreur: "AADSTS65001: consent required"

**Cause :** Permissions manquantes ou non acceptées

**Solution :**
1. Vérifier que toutes les permissions sont ajoutées dans Azure AD
2. Lors de la première connexion depuis Odoo, accepter les permissions
3. Si la page de consentement n'apparaît pas :
   - Odoo > Calendrier > Déconnecter Outlook
   - Se reconnecter

### Erreur: "redirect_uri_mismatch"

**Cause :** L'URL de redirection ne correspond pas

**Solution :**

Vérifier que dans Azure AD vous avez exactement :
```
http://localhost:8069/microsoft_account/authentication
```

Et que Odoo tourne bien sur :
```
http://localhost:8069
```

**Attention aux détails :**
- ❌ `https://localhost` (https au lieu de http)
- ❌ `http://localhost:8069/` (slash final en trop)
- ❌ `http://127.0.0.1:8069` (IP au lieu de localhost)
- ✅ `http://localhost:8069/microsoft_account/authentication` (correct)

---

## Récapitulatif rapide

### Pour tester en 15 minutes (localhost)

```
1. ✅ Créer compte Outlook.com gratuit
2. ✅ Créer app Azure AD avec redirect http://localhost:8069/...
3. ✅ Copier Client ID et Secret
4. ✅ Lancer Odoo localement
5. ✅ Configurer les credentials dans Odoo
6. ✅ Tester la connexion Outlook
7. ✅ Importer test_events.ics
8. ✅ Lancer une synchronisation
9. ✅ Consulter les rapports et l'analyse
10. ✅ Vérifier le bug année 9992
```

**Total: 15 minutes, 0€** 🎉

### Ce qu'il NE FAUT PAS

- ❌ Acheter Office 365 pour tester
- ❌ Acheter un domaine pour tester
- ❌ Configurer SSL pour tester localement
- ❌ Utiliser votre compte Outlook professionnel réel
- ❌ Ouvrir des ports firewall pour localhost
- ❌ Chercher "offline_access" dans Azure AD

### Ce qu'il FAUT

- ✅ Compte Microsoft gratuit (Outlook.com)
- ✅ Application Azure AD (gratuite)
- ✅ Odoo qui tourne (localhost suffit)
- ✅ Redirect URI configuré dans Azure
- ✅ Client ID et Secret dans Odoo
- ✅ C'est tout !

---

## Ressources

- **Documentation module** : `README.md`
- **Issue technique pour Odoo** : `ISSUE_ODOO.md`
- **Synthèse client** : `SYNTHESE_CLIENT.md`
- **Documentation Microsoft** : https://docs.microsoft.com/graph
- **Azure Portal** : https://portal.azure.com
- **ngrok** : https://ngrok.com
