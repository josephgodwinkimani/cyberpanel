Server_IP=$(curl --silent --max-time 30 -4 https://wtfismyip.com/text) 
echo "$Server_IP" > "/etc/cyberpanel/machineIP"