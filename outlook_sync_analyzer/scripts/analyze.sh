#!/bin/bash
# Script d'analyse rapide de la synchronisation Outlook
# Usage: ./analyze.sh database_name

set -e

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Vérifier les arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 database_name [output_file]"
    echo "Exemple: $0 production_db /tmp/rapport.md"
    exit 1
fi

DATABASE=$1
OUTPUT=${2:-"/tmp/outlook_sync_report_$(date +%Y%m%d_%H%M%S).md"}

echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Analyse de synchronisation Outlook - $DATABASE${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo

# Fonction pour exécuter une requête SQL
run_sql() {
    sudo -u postgres psql -d "$DATABASE" -t -c "$1"
}

# Fonction pour afficher un résultat avec couleur
show_result() {
    local label=$1
    local value=$2
    local threshold=${3:-0}

    if [ "$value" -gt "$threshold" ]; then
        echo -e "${label}: ${RED}${value}${NC}"
    else
        echo -e "${label}: ${GREEN}${value}${NC}"
    fi
}

echo -e "${YELLOW}[1/5] Statistiques globales...${NC}"

# Total événements
TOTAL_EVENTS=$(run_sql "SELECT COUNT(*) FROM calendar_event;")
SYNCED_EVENTS=$(run_sql "SELECT COUNT(*) FROM calendar_event WHERE microsoft_id IS NOT NULL;")
NEED_SYNC=$(run_sql "SELECT COUNT(*) FROM calendar_event WHERE need_sync_m = true;")
STUCK=$(run_sql "SELECT COUNT(*) FROM calendar_event WHERE need_sync_m = true AND write_date < NOW() - INTERVAL '7 days';")
EXTREME_FUTURE=$(run_sql "SELECT COUNT(*) FROM calendar_event WHERE EXTRACT(YEAR FROM stop) > 2030;")

echo
show_result "  Total événements" "$TOTAL_EVENTS" 0
show_result "  Synchronisés" "$SYNCED_EVENTS" 0
show_result "  À synchroniser (need_sync_m)" "$NEED_SYNC" 50
show_result "  Bloqués (>7 jours)" "$STUCK" 10
show_result "  Futur extrême (>2030)" "$EXTREME_FUTURE" 0
echo

# Vérifier si problèmes critiques
CRITICAL=0
if [ "$STUCK" -gt 50 ]; then
    echo -e "${RED}⚠️  CRITIQUE: $STUCK événements bloqués depuis plus de 7 jours !${NC}"
    CRITICAL=1
fi

if [ "$EXTREME_FUTURE" -gt 10 ]; then
    echo -e "${RED}⚠️  CRITIQUE: $EXTREME_FUTURE événements avec dates futures extrêmes !${NC}"
    CRITICAL=1
fi

if [ $CRITICAL -eq 0 ]; then
    echo -e "${GREEN}✓ Aucun problème critique détecté${NC}"
fi
echo

echo -e "${YELLOW}[2/5] Utilisateurs avec synchronisation Outlook...${NC}"
USERS_COUNT=$(run_sql "SELECT COUNT(*) FROM res_users WHERE microsoft_calendar_rtoken IS NOT NULL;")
echo -e "  Utilisateurs configurés: ${BLUE}${USERS_COUNT}${NC}"
echo

# Top 5 des utilisateurs avec événements bloqués
echo -e "${YELLOW}[3/5] Top 5 utilisateurs avec événements bloqués...${NC}"
run_sql "
SELECT
    RPAD(ru.name, 30) || ' | ' || LPAD(COUNT(*)::text, 5) || ' événements bloqués'
FROM calendar_event ce
JOIN calendar_event_res_partner_rel cepr ON cepr.calendar_event_id = ce.id
JOIN res_partner rp ON rp.id = cepr.res_partner_id
JOIN res_users ru ON ru.partner_id = rp.id
WHERE ce.need_sync_m = true
AND ce.write_date < NOW() - INTERVAL '7 days'
GROUP BY ru.id, ru.name
ORDER BY COUNT(*) DESC
LIMIT 5;
" | while read line; do
    echo "  $line"
done
echo

# Récurrences anormales
if [ "$EXTREME_FUTURE" -gt 0 ]; then
    echo -e "${YELLOW}[4/5] Exemples de récurrences anormales (top 10)...${NC}"
    run_sql "
    SELECT
        RPAD(COALESCE(name, 'Sans nom'), 40) || ' | ' ||
        TO_CHAR(stop, 'YYYY-MM-DD') || ' | Année: ' ||
        EXTRACT(YEAR FROM stop)::text
    FROM calendar_event
    WHERE EXTRACT(YEAR FROM stop) > 2030
    ORDER BY stop DESC
    LIMIT 10;
    " | while read line; do
        echo -e "  ${RED}$line${NC}"
    done
    echo
fi

# Paramètres de synchronisation actuels
echo -e "${YELLOW}[5/5] Paramètres de synchronisation actuels...${NC}"
RANGE_DAYS=$(run_sql "SELECT value FROM ir_config_parameter WHERE key = 'microsoft_calendar.sync.range_days';")
LOWER_BOUND=$(run_sql "SELECT value FROM ir_config_parameter WHERE key = 'microsoft_calendar.sync.lower_bound_range';")
FIRST_SYNC=$(run_sql "SELECT value FROM ir_config_parameter WHERE key = 'microsoft_calendar.sync.first_synchronization_date';")

echo "  Plage de synchronisation: ${RANGE_DAYS:-365 (défaut)} jours"
echo "  Borne inférieure: ${LOWER_BOUND:-Non défini}"
echo "  Date première sync: ${FIRST_SYNC:-Non défini}"
echo

# Recommandations
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Recommandations${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo

if [ "$STUCK" -gt 10 ]; then
    echo -e "${YELLOW}1. Installer le module outlook_sync_analyzer pour tracer les problèmes${NC}"
    echo "   Apps > Update Apps List > Chercher 'Outlook Sync Analyzer'"
    echo
fi

if [ "${RANGE_DAYS:-365}" -gt 60 ]; then
    echo -e "${YELLOW}2. Réduire la plage de synchronisation${NC}"
    echo "   Paramètres > Outlook Sync Analyzer"
    echo "   Recommandé: 30 jours au lieu de ${RANGE_DAYS:-365}"
    echo
fi

if [ "$EXTREME_FUTURE" -gt 0 ]; then
    echo -e "${YELLOW}3. Nettoyer les récurrences anormales${NC}"
    echo "   ATTENTION: Faire un backup avant !"
    echo "   DELETE FROM calendar_event WHERE EXTRACT(YEAR FROM stop) > 2030;"
    echo
fi

if [ "$STUCK" -gt 30 ]; then
    echo -e "${YELLOW}4. Réinitialiser les événements bloqués depuis longtemps${NC}"
    echo "   UPDATE calendar_event"
    echo "   SET need_sync_m = false"
    echo "   WHERE need_sync_m = true"
    echo "   AND write_date < NOW() - INTERVAL '30 days';"
    echo
fi

# Générer le rapport complet avec le script Python si disponible
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Génération du rapport complet...${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_SCRIPT="$SCRIPT_DIR/production_analysis.py"

if [ -f "$PYTHON_SCRIPT" ]; then
    echo "Génération du rapport détaillé..."
    if python3 "$PYTHON_SCRIPT" --database "$DATABASE" --output "$OUTPUT"; then
        echo -e "${GREEN}✓ Rapport généré: $OUTPUT${NC}"
        echo
        echo "Consulter le rapport pour plus de détails:"
        echo "  cat $OUTPUT"
        echo "  ou"
        echo "  less $OUTPUT"
    else
        echo -e "${RED}✗ Erreur lors de la génération du rapport Python${NC}"
    fi
else
    echo -e "${YELLOW}Script Python non trouvé, rapport SQL seulement${NC}"

    # Générer un rapport markdown basique
    cat > "$OUTPUT" << EOF
# Rapport d'analyse Outlook Sync - $DATABASE

**Date:** $(date)
**Généré par:** analyse.sh

## Statistiques globales

- Total événements: $TOTAL_EVENTS
- Synchronisés: $SYNCED_EVENTS
- À synchroniser (need_sync_m): $NEED_SYNC
- Bloqués (>7 jours): $STUCK
- Futur extrême (>2030): $EXTREME_FUTURE

## Configuration actuelle

- Plage de synchronisation: ${RANGE_DAYS:-365 (défaut)} jours
- Borne inférieure: ${LOWER_BOUND:-Non défini}
- Date première sync: ${FIRST_SYNC:-Non défini}

## Actions recommandées

1. Installer le module outlook_sync_analyzer
2. Réduire la plage de synchronisation à 30 jours
3. Nettoyer les récurrences anormales (>2030)
4. Réinitialiser les événements bloqués (>30 jours)

## Pour plus de détails

Utiliser le script Python:
\`\`\`bash
python3 $SCRIPT_DIR/production_analysis.py --database $DATABASE --output rapport_detail.md
\`\`\`
EOF

    echo -e "${GREEN}✓ Rapport basique généré: $OUTPUT${NC}"
fi

echo
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}   Analyse terminée !${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"

# Retourner le code d'erreur si problèmes critiques
exit $CRITICAL
