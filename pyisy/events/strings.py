"""Strings for Event Stream Requests."""

# Subscribe Message
SUB_MSG = {
    "head": """POST /services HTTP/1.1
Host: {addr}:{port}{webroot}
Authorization: {auth}
Content-Length: {length}
Content-Type: text/xml; charset="utf-8"
SOAPAction: urn:udi-com:device:X_Insteon_Lighting_Service:1#Subscribe\r
\r
""",
    "body": """<s:Envelope><s:Body>
<u:Subscribe xmlns:u="urn:udi-com:service:X_Insteon_Lighting_Service:1">
<reportURL>REUSE_SOCKET</reportURL>
<duration>infinite</duration>
</u:Subscribe></s:Body></s:Envelope>
\r
""",
}

# Unsubscribe Message
UNSUB_MSG = {
    "head": """POST /services HTTP/1.1
Host: {addr}:{port}{webroot}
Authorization: {auth}
Content-Length: {length}
Content-Type: text/xml; charset="utf-8"
SOAPAction: urn:udi-com:device:X_Insteon_Lighting_Service:1#Unsubscribe\r
\r
""",
    "body": """<s:Envelope><s:Body>
<u:Unsubscribe xmlns:u="urn:udi-com:service:X_Insteon_Lighting_Service:1">
<SID>{sid}</SID>
</u:Unsubscribe></s:Body></s:Envelope>
\r
""",
}

# Resubscribe Message
RESUB_MSG = {
    "head": """POST /services HTTP/1.1
Host: {addr}:{port}{webroot}
Authorization: {auth}
Content-Length: {length}
Content-Type: text/xml; charset="utf-8"
SOAPAction: urn:udi-com:device:X_Insteon_Lighting_Service:1#Subscribe\r
\r
""",
    "body": """<s:Envelope><s:Body>
<u:Subscribe xmlns:u="urn:udi-com:service:X_Insteon_Lighting_Service:1">
<reportURL>REUSE_SOCKET</reportURL>
<duration>infinite</duration>
<SID>{sid}</SID>
</u:Subscribe></s:Body></s:Envelope>
\r
""",
}
