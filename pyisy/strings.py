"""Strings for Event Stream Requests."""

# Subscribe Message
SUB_MSG = {
    "head": """POST /services HTTP/1.1\r
Host: {addr}:{port}\r
Authorization: Basic {auth}\r
Content-Length: {length}\r
Content-Type: text/xml\r
charset="utf-8"\r
\r
\r
""",
    "body": """<s:Envelope><s:Body>\r
<u:Subscribe xmlns:u="urn:udicom:service:X_Insteon_Lighting_Service:1">\r
<reportURL>REUSE_SOCKET</reportURL>\r
<duration>infinite</duration>\r
</u:Subscribe></s:Body></s:Envelope>""",
}

# Unsubscribe Message
UNSUB_MSG = {
    "head": """POST /services HTTP/1.1\r
Host: {addr}:{port}\r
Authorization: Basic {auth}\r
Content-Length: 195\r
Content-Type: text/xml\r
charset="utf-8"\r
\r
\r
""",
    "body": """<s:Envelope><s:Body>\r
<u:Unsubscribe xmlns:u="urn:udicom:service:X_Insteon_Lighting_Service:1">\r
<SID>{sid}</SID>\r
</u:Subscribe></s:Body></s:Envelope>""",
}

# Resubscribe Message
RESUB_MSG = {
    "head": """POST /services HTTP/1.1\r
Host: {addr}:{port}\r
Authorization: Basic {auth}\r
Content-Length: {length}\r
Content-Type: text/xml\r
charset="utf-8"\r
\r
\r
""",
    "body": """<s:Envelope><s:Body>\r
<u:Subscribe xmlns:u="urn:udicom:service:X_Insteon_Lighting_Service:1">\r
<reportURL>REUSE_SOCKET</reportURL>\r
<duration>infinite</duration>\r
<SID>{sid}</SID>\r
</u:Subscribe></s:Body></s:Envelope>""",
}
