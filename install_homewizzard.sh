#!/bin/bash
# ============================================================
# HomeWizard Energy P1 - Automatisch installatiescript
# Voor Victron Cerbo GX (Venus OS)
# Versie 1.1 - Met nettype selectie
# ============================================================

clear
echo ""
echo "============================================================"
echo "  HomeWizard Energy P1 - Victron Cerbo GX"
echo "============================================================"
echo ""
echo "Wat wil je doen?"
echo ""
echo "  1. Installeren"
echo "  2. Deinstalleren"
echo ""
read -p "Keuze (1 of 2): " KEUZE
echo ""

# ============================================================
# DEINSTALLEREN
# ============================================================
if [ "$KEUZE" == "2" ]; then
    echo "============================================================"
    echo "  Deinstallatie"
    echo "============================================================"
    echo ""

    if [ ! -d "/data/dbus-Home-Wizzard-Energy-P1" ]; then
        echo "Geen installatie gevonden. Niets te verwijderen."
        exit 0
    fi

    read -p "Ben je zeker dat je de HomeWizard P1 wilt verwijderen? (j/n): " CONFIRM
    if [[ "$CONFIRM" != "j" && "$CONFIRM" != "J" ]]; then
        echo "Deinstallatie geannuleerd."
        exit 0
    fi

    echo ""
    echo "Service stoppen..."
    svc -d /service/dbus-home-wizzard-energy-p1 2>/dev/null
    sleep 2
    echo "Uninstall script uitvoeren..."
    /data/dbus-Home-Wizzard-Energy-P1/uninstall.sh 2>/dev/null
    echo "Symlink verwijderen..."
    rm -f /service/dbus-home-wizzard-energy-p1
    echo "Bestanden verwijderen..."
    rm -rf /data/dbus-Home-Wizzard-Energy-P1
    echo "Zip opruimen..."
    rm -f ~/main.zip

    echo ""
    echo "Verificatie:"
    [ ! -d "/data/dbus-Home-Wizzard-Energy-P1" ] && echo "✓ Map verwijderd" || echo "✗ Map nog aanwezig"
    svstat /service/dbus-home-wizzard-energy-p1 2>&1 | grep -q "file does not exist" && echo "✓ Service verwijderd" || echo "✗ Service nog actief"

    echo ""
    echo "============================================================"
    echo "  Deinstallatie voltooid!"
    echo "============================================================"
    exit 0
fi

# ============================================================
# INSTALLEREN
# ============================================================
if [ "$KEUZE" != "1" ]; then
    echo "Ongeldige keuze. Script afgesloten."
    exit 1
fi

clear
echo ""
echo "============================================================"
echo "  Installatie - Stap 1: Nettype selecteren"
echo "============================================================"
echo ""
echo "Welk type elektriciteitsnet heeft deze installatie?"
echo ""
echo "  1. 3x400V    - Standaard 3-fase met nulgeleider (Fluvius)"
echo "                 L1, L2 en L3 worden correct uitgelezen"
echo ""
echo "  2. Mono 230V - Enkelfasig net"
echo "                 Enkel L1 wordt uitgelezen"
echo ""
echo "  3. 3x230V    - 3-fase zonder nulgeleider (LGF5E360 meter)"
echo "                 L1/L2/L3 vermogen = 0, scriptfix nodig"
echo ""
read -p "Keuze (1, 2 of 3): " NETTYPE
echo ""

case $NETTYPE in
    1) PHASES="3"; SCRIPTFIX="nee"; NETLABEL="3x400V" ;;
    2) PHASES="1"; SCRIPTFIX="nee"; NETLABEL="Mono 230V" ;;
    3) PHASES="1"; SCRIPTFIX="ja";  NETLABEL="3x230V" ;;
    *) echo "Ongeldige keuze. Script afgesloten."; exit 1 ;;
esac

echo "Geselecteerd: $NETLABEL → Phases = $PHASES, Scriptfix = $SCRIPTFIX"
echo ""

echo "============================================================"
echo "  Installatie - Stap 2: IP-adres invullen"
echo "============================================================"
echo ""
echo "Tip: Controleer het IP via de HomeWizard app"
echo "     of surf naar http://[IP]/api/v1/data om te testen"
echo ""
read -p "IP-adres van de HomeWizard P1 (bv. 192.168.0.247): " P1_IP

if [[ ! $P1_IP =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo ""
    echo "FOUT: Ongeldig IP-adres '$P1_IP'"
    echo "      Controleer het adres en probeer opnieuw."
    exit 1
fi

echo ""
echo "============================================================"
echo "  Overzicht configuratie"
echo "============================================================"
echo ""
echo "  IP P1:     $P1_IP"
echo "  Nettype:   $NETLABEL"
echo "  Phases:    $PHASES"
echo "  Scriptfix: $SCRIPTFIX"
echo ""
read -p "Is dit correct? (j/n): " CONFIRM
if [[ "$CONFIRM" != "j" && "$CONFIRM" != "J" ]]; then
    echo "Installatie geannuleerd."
    exit 1
fi

echo ""
echo "============================================================"
echo "  Stap 3 - P1 verbinding testen"
echo "============================================================"

curl -s --connect-timeout 5 "http://$P1_IP/api/v1/data" > /tmp/p1_test.json 2>/dev/null
if [ $? -ne 0 ] || [ ! -s /tmp/p1_test.json ]; then
    echo ""
    echo "FOUT: HomeWizard P1 niet bereikbaar op $P1_IP"
    echo "      Controleer het IP-adres, WiFi en netwerk."
    exit 1
fi
echo "✓ P1 bereikbaar op $P1_IP"

echo ""
echo "============================================================"
echo "  Stap 4 - Oude installatie controleren"
echo "============================================================"

if [ -d "/data/dbus-Home-Wizzard-Energy-P1" ]; then
    echo "Bestaande installatie gevonden - verwijderen..."
    svc -d /service/dbus-home-wizzard-energy-p1 2>/dev/null
    sleep 2
    /data/dbus-Home-Wizzard-Energy-P1/uninstall.sh 2>/dev/null
    rm -f /service/dbus-home-wizzard-energy-p1
    rm -rf /data/dbus-Home-Wizzard-Energy-P1
    echo "✓ Oude installatie verwijderd"
else
    echo "✓ Geen bestaande installatie gevonden"
fi

echo ""
echo "============================================================"
echo "  Stap 5 - Software downloaden"
echo "============================================================"

cd /root && rm -f main.zip
wget -q --show-progress https://github.com/back2basic/dbus-Home-Wizzard-Energy-P1/archive/refs/heads/main.zip

if [ $? -ne 0 ]; then
    echo "FOUT: Download mislukt. Controleer de internetverbinding."
    exit 1
fi
echo "✓ Download geslaagd"

echo ""
echo "============================================================"
echo "  Stap 6 - Uitpakken"
echo "============================================================"

unzip -q main.zip "dbus-Home-Wizzard-Energy-P1-main/*" -d /data
mv /data/dbus-Home-Wizzard-Energy-P1-main /data/dbus-Home-Wizzard-Energy-P1
chmod a+x /data/dbus-Home-Wizzard-Energy-P1/install.sh
chmod a+x /data/dbus-Home-Wizzard-Energy-P1/restart.sh
chmod a+x /data/dbus-Home-Wizzard-Energy-P1/uninstall.sh
echo "✓ Uitpakken geslaagd"

echo ""
echo "============================================================"
echo "  Stap 7 - Configuratie aanpassen"
echo "============================================================"

sed -i "s/Host=10.20.31.10/Host=$P1_IP/" /data/dbus-Home-Wizzard-Energy-P1/config.ini
sed -i "s/Phases = 1/Phases = $PHASES/" /data/dbus-Home-Wizzard-Energy-P1/config.ini

echo "✓ Config aangemaakt:"
echo "  $(grep Host= /data/dbus-Home-Wizzard-Energy-P1/config.ini)"
echo "  $(grep Phases /data/dbus-Home-Wizzard-Energy-P1/config.ini)"

if [ "$SCRIPTFIX" == "ja" ]; then
    echo ""
    echo "============================================================"
    echo "  Stap 8 - Scriptfix toepassen (3x230V / LGF5E360)"
    echo "============================================================"

python3 << 'PYEOF'
with open('/data/dbus-Home-Wizzard-Energy-P1/dbus-home-wizzard-energy-p1.py', 'r') as f:
    content = f.read()
old1 = "self._dbusservice['/Ac/L1/Power'] = meter_data['active_power_l1_w']"
new1 = "self._dbusservice['/Ac/L1/Power'] = meter_data['active_power_w']"
content = content.replace(old1, new1, 1)
old2 = "self._dbusservice['/Ac/L1/Power'] = meter_data['active_power_w']"
new2 = """self._dbusservice['/Ac/L1/Power'] = meter_data['active_power_w']
                self._dbusservice['/Ac/L2/Power']   = 0
                self._dbusservice['/Ac/L3/Power']   = 0
                self._dbusservice['/Ac/L2/Voltage'] = 0
                self._dbusservice['/Ac/L3/Voltage'] = 0
                self._dbusservice['/Ac/L2/Current'] = 0
                self._dbusservice['/Ac/L3/Current'] = 0"""
content = content.replace(old2, new2, 1)
with open('/data/dbus-Home-Wizzard-Energy-P1/dbus-home-wizzard-energy-p1.py', 'w') as f:
    f.write(content)
print("✓ Scriptfix geslaagd")
PYEOF
else
    echo ""
    echo "Stap 8 - Scriptfix: niet nodig voor $NETLABEL ✓"
fi

echo ""
echo "============================================================"
echo "  Stap 9 - Service installeren"
echo "============================================================"

/data/dbus-Home-Wizzard-Energy-P1/install.sh
rm -f /service/dbus-home-wizzard-energy-p1
ln -s /data/dbus-Home-Wizzard-Energy-P1/service /service/dbus-home-wizzard-energy-p1
sleep 3
echo "✓ Service geinstalleerd en gestart"

echo ""
echo "============================================================"
echo "  Stap 10 - Verificatie"
echo "============================================================"
echo ""

svstat /service/dbus-home-wizzard-energy-p1 2>&1 | grep -q "up" && echo "✓ Service draait" || echo "✗ Service draait NIET"

sleep 3
POWER=$(dbus -y com.victronenergy.grid.http_40 /Ac/Power GetValue 2>/dev/null)
[ -n "$POWER" ] && echo "✓ Netmeting actief: $POWER W" || echo "✗ DBus geeft nog geen waarde - wacht 10 sec en controleer opnieuw"

LOG_ERRORS=$(grep "CRITICAL" /data/dbus-Home-Wizzard-Energy-P1/current.log 2>/dev/null | tail -3)
[ -z "$LOG_ERRORS" ] && echo "✓ Log: geen fouten" || echo "✗ Log fouten: $LOG_ERRORS"

echo ""
echo "============================================================"
echo "  Installatie voltooid!"
echo ""
echo "  Controleer het VRM dashboard:"
echo "  - Remote Console: http://[IP van Cerbo]"
echo "  - VRM Portaal:    https://vrm.victronenergy.com"
echo "============================================================"
echo ""

echo ""
read -p "Wil je de Cerbo nu herstarten? (aanbevolen) (j/n): " REBOOT
if [[ "$REBOOT" == "j" || "$REBOOT" == "J" ]]; then
    echo ""
    echo "Cerbo wordt herstart... Verbinding wordt verbroken."
    echo "Wacht 60 seconden en verbind opnieuw via PuTTY."
    sleep 3
    reboot
else
    echo ""
    echo "Geen herstart. Controleer het VRM dashboard."
fi
