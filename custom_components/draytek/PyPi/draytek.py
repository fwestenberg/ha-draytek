"""This component provides basic support for a DrayTek WiFi router."""
import logging
import voluptuous as vol
from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNAVAILABLE
import urllib.parse
import requests
import base64
import random
import string
import re
import time

WIFI_ENABLED=805306372
WIFI_DISABLED=805306368

_LOGGER = logging.getLogger(__name__)

class routerDevice():
    """An implementation of a DrayTek WiFi Router."""

    def __init__(self, host, username, password):
        super().__init__()

        self._host = host
        self._username = self.encode(username)
        self._password = self.encode(password)
        self._sFormAuthStr = self.randomString()
        self._state = STATE_OFF
        self._session = None
        self._cookies = None
        self._headers = {}
        self._config = {}

    def randomString(self):
        """Generate a random string of fixed length """
        lettersAndDigits = string.ascii_letters + string.digits
        return ''.join(random.choice(lettersAndDigits) for i in range(15))
    
    def encode(self, encodeStr):
        return base64.b64encode(encodeStr.encode()).decode('ascii')

    def login(self):
        # The default login header
        self._headers = {
            "POST": "/cgi-bin/wlogin.cgi HTTP/1.1",
            "Host": self._host,
            "Connection": "keep-alive",
            "Content-Length": "102",
            "Cache-Control": "max-age=0",
            "Origin": f"http://{self._host}",
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Referer": f"http://{self._host}/weblogin.htm",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7,de;q=0.6",
        }

        with requests.Session() as s:
            payload = {"aa": self._username, "ab": self._password, "sslgroup": "-1", "sFormAuthStr": self._sFormAuthStr, "obj4": "", "obj5": "", "obj6": "", "obj7": "", "obj8": ""}
            url=f"http://{self._host}/cgi-bin/wlogin.cgi"

            try:
                r = s.post(
                    url=url, 
                    headers=self._headers,
                    data=payload,
                    allow_redirects=False,
                    timeout=10
                )
            except requests.exceptions.RequestException: 
                _LOGGER.error(f"Error while connecting with DrayTek IP {self._host}")

            if r.is_redirect:
                self._session = s
                self._cookies = r.cookies
            else:   
                _LOGGER.error(f"Login failed at DrayTek IP {self._host}")
                s.close()
                return False 

            if len(self._cookies) == 0:
                s.close()
                _LOGGER.error(f"No Cookies available for DrayTek IP {self._host}")
            else:
                _LOGGER.info(f"Login success at DrayTek IP {self._host}")
                return True

    def logout(self):
        if self._session is not None:
            self._session.close()

    def get_wifi_state(self, keepAlive=False):
        url = f"http://{self._host}/cgi-bin/V2X00.cgi?sFormAuthStr={self._sFormAuthStr}&fid=3001"

        if not self.login():
            self._state = STATE_UNAVAILABLE
            return self._state

        url = f"http://{self._host}/doc/wlguestwifi.htm"
        self._headers["Referer"] = f"http://{self._host}/menu.htm"

        try:
            r = self._session.get(
                url=url, 
                headers=self._headers,
                cookies=self._cookies,
                allow_redirects=False,
                timeout=10
            )
        except requests.exceptions.RequestException: 
            _LOGGER.error(f"Error while connecting with DrayTek IP {self._host}")
            self._state = STATE_UNAVAILABLE
            return self._state

        try:
            wifiEnabled = int(re.search("var specialflag='(.+?)';", r.text).group(1))
            sSpotName = re.search("var SSID3='(.+?)';", r.text).group(1)
            sSpotPwd = re.search('var sDftWEPKey="(.+?)";', r.text).group(1)
            rateControl = int(re.search("var iRateCtl='(.+?)';", r.text).group(1))
            sUpRate = int(re.search("var iRxRate2='(.+?)';", r.text).group(1)) * 100
            sDownRate = int(re.search("var iTxRate2='(.+?)';", r.text).group(1)) * 100
            autoProv = int(re.search('var iApmFlags="(.+?)";', r.text).group(1))
        except AttributeError:
            _LOGGER.error(f"Failed to enquire the current state values at DrayTek IP {self._host}")
            self._state = STATE_UNAVAILABLE
            return self._state

        self._config["sSpotName"] = sSpotName
        self._config["sSpotPwd"] = sSpotPwd
        self._config["sUpRate"] = sUpRate
        self._config["sDownRate"] = sDownRate
        self._config["fid"] = 3001
        self._config["sWlessPSK"] = ''
        self._config["iAct"] = 1
        self._config["sFormAuthStr"] = self._sFormAuthStr

        if rateControl == 4:
            self._config["rateCtlEn"] = 1
        else:
            self._config["rateCtlEn"] = 0

        if autoProv == 0:
            self._config["enAutoProv"] = 1
        else:
            self._config["enAutoProv"] = 0

        if wifiEnabled == WIFI_ENABLED:
            self._config["gstWifiEn"] = 1
            self._state = STATE_ON
        elif wifiEnabled == WIFI_DISABLED:
            self._config["gstWifiEn"] = 0
            self._state = STATE_OFF
        else:
            _LOGGER.error(f"Unknown WiFi state value: {wifiEnabled} for DrayTek IP: {self._host}")
            self._state = STATE_UNAVAILABLE
            return self._state

        # print(f"Current config: {self._config}")

        if not keepAlive:
            self.logout()

        return self._state

    async def set_wifi_state(self, setState):
        # Wait some seconds before restarting all WiFi adapters
        time.sleep(3)

        if self.get_wifi_state() == STATE_UNAVAILABLE:
            return

        url = f"http://{self._host}/cgi-bin/V2X00.cgi"
        self._headers["Referer"] = f"http://{self._host}/doc/wlguestwifi.htm"
        config = self._config.copy()

        if setState == STATE_ON:
            config["gstWifiEn"] = 1
        else:
            config["gstWifiEn"] = 0

        # print(f"Updated config: {config}")

        try:
            r = self._session.post(
                url=url, 
                headers=self._headers,
                data=config,
                cookies=self._cookies,
                allow_redirects=False,
                timeout=60
            )
        except requests.exceptions.RequestException: 
            _LOGGER.error(f"Error while connecting with DrayTek IP {self._host}")
            setState = STATE_UNAVAILABLE
        
        self.logout()

        _LOGGER.info(f"WiFi update response code {r.status_code} {r.text}")

        if r.status_code == 302:
            self._state = setState
            self._config = config
        else:
            _LOGGER.error(f"Failed to change the WiFi state at DrayTek IP {self._host}")
