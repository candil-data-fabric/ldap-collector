__name__ = "LDAP Collector"
__version__ = "2.2.1"
__author__ = "David Martínez García"
__credits__ = ["GIROS DIT-UPM", "Luis Bellido Triana", "Daniel González Sánchez", "David Martínez García"]

## -- BEGIN IMPORT STATEMENTS -- ##

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
import json
from ldap3 import Server, Connection, ALL, ALL_ATTRIBUTES
import logging
import time
import os

## -- END IMPORT STATEMENTS -- ##

## -- BEGIN CONSTANTS DECLARATION -- ##

# LDAP DN of the organization to retrieve information from:
LDAP_ORGANIZATION_DN = os.getenv("LDAP_ORGANIZATION_DN")

# URI where the LDAP server is listening for incoming connections or requests:
# FORMAT: ldap(s)://<ip_or_fqdn>:<port>.
# LDAP (unencrypted) port is 389. LDAPS (encrypted) port is 636.
LDAP_SERVER_ENDPOINT = os.getenv("LDAP_SERVER_ENDPOINT")

# Whether or not to use SSL for the connection with the server:
LDAP_USE_SSL = os.getenv("LDAP_USE_SSL", "False") == "True"

# LDAP DN and password of the user for connecting with the server and retrieving information:
LDAP_USER = os.getenv("LDAP_USER")
LDAP_PASSWORD = os.getenv("LDAP_PASSWORD")

# Maximum number of times the client will try to establish a connection with the LDAP server:
LDAP_CONN_MAX_RETRIES = os.getenv("LDAP_CONN_MAX_RETRIES")

# Time (in seconds) to wait between retries while trying to establish a connection with the LDAP server:
LDAP_CONN_TIMEOUT = os.getenv("LDAP_CONN_TIMEOUT")

## -- END CONSTANTS DECLARATION -- ##

## -- BEGIN LOGGING CONFIGURATION -- ## 

logger = logging.getLogger(__name__)
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.DEBUG,
    datefmt='%Y-%m-%d %H:%M:%S')

## -- END LOGGING CONFIGURATION -- ##

## -- BEGIN DEFINITION OF AUXILIARY FUNCTIONS AND VARIABLES -- ##

def establish_connection(server: Server, user: str, password: str, max_retries: int, timeout: int) -> Connection:
    """
    Tries to establish a connection to the LDAP server.
    This function will try to establish the connection within a maximum number of retries of specified timeout.
    """
    logger.info("Trying to establish a connection to the following LDAP server: " + str(server))

    for retry in range(1, max_retries + 1):
        try:
            logger.info("Retry: " + str(retry))
            connection = Connection(server, user, password, auto_bind=True)
        except Exception as e:
            logger.exception("The connection to the LDAP server could not be established: %s" % e)
            if retry == max_retries:
                raise RuntimeError("The connection to the LDAP server could not be established: %s" % e)
            else:
                logger.info("Waiting " + str(timeout) + " seconds before trying again")
                time.sleep(timeout)
                continue
        if connection is not None:
            logger.info("Connection sucessfully established")
            break
    
    return connection

def retrieve_information(connection: Connection, organization_dn: str):
    """
    Retrieves LDAP information for users, roles, groups and organizations, and returns it JSON objects.
    """
    logger.info("Trying to retrieve LDAP information...")

    # Retrieve users:
    try:
        logger.info("Trying to retrieve LDAP information for users...")
        users = connection.search('ou=users,' + organization_dn, "(objectclass=*)", attributes=ALL_ATTRIBUTES)
        users = connection.response_to_json(users)
        users = json.loads(users)
    except Exception as e:
        logger.exception("Exception while retrieving LDAP information for users: %s" % e)
        raise RuntimeError("Exception while retrieving LDAP information for users: %s" % e)
    logger.info("LDAP information for users successfully retrieved")

    # Retrieve roles:
    try:
        logger.info("Trying to retrieve LDAP information for roles...")
        roles = connection.search('ou=roles,' + organization_dn, "(objectclass=*)", attributes=ALL_ATTRIBUTES)
        roles = connection.response_to_json(roles)
        roles = json.loads(roles)
    except Exception as e:
        logger.exception("Exception while retrieving LDAP information for roles: %s" % e)
        raise RuntimeError("Exception while retrieving LDAP information for roles: %s" % e)
    logger.info("LDAP information for roles successfully retrieved")

    # Retrieve groups:
    try:
        logger.info("Trying to retrieve LDAP information for groups...")
        groups = connection.search('ou=groups,' + organization_dn, "(objectclass=*)", attributes=ALL_ATTRIBUTES)
        groups = connection.response_to_json(groups)
        groups = json.loads(groups)
    except Exception as e:
        logger.exception("Exception while retrieving LDAP information for groups: %s" % e)
        raise RuntimeError("Exception while retrieving LDAP information for groups: %s" % e)
    logger.info("LDAP information for groups successfully retrieved")

    # Retrieve organizations:
    try:
        logger.info("Trying to retrieve LDAP information for organizations...")
        orgs = connection.search(organization_dn, "(objectclass=organization)", attributes=ALL_ATTRIBUTES)
        orgs = connection.response_to_json(orgs)
        orgs = json.loads(orgs)
    except Exception as e:
        logger.exception("Exception while retrieving LDAP information for organizations: %s" % e)
        raise RuntimeError("Exception while retrieving LDAP information for organizations: %s" % e)
    logger.info("LDAP information for organizations successfully retrieved")

    logger.info("LDAP information retrieved")

    return users, roles, groups, orgs

def generate_json(users, roles, groups, orgs, organization_dn) -> dict:
    """
    Processes every individual JSON object, passed as arguments, and generates a single
    JSON object with the LDAP information.
    """
    logger.info("Generating JSON object with LDAP information...")

    ldap_json = {}
    ldap_json["users"] = []
    ldap_json["roles"] = []
    ldap_json["groups"] = []
    ldap_json["organizations"] = []
    ldap_json["memberships"] = []
    
    # -- Users --
    for entry in range(1, len(users["entries"])):
        user = {}
        user["dn"] = users["entries"][entry]["dn"]
        user["attributes"] = {}
        for raw_attribute in users["entries"][entry]["raw"]:
            if (raw_attribute == 'objectClass'):
                user["attributes"][raw_attribute] = users["entries"][entry]["raw"][raw_attribute]
            else:
                user["attributes"][raw_attribute] = users["entries"][entry]["raw"][raw_attribute][0]
        splitted_given_name = user["attributes"]["givenName"].split()
        if (len(splitted_given_name) < 2):
            first_name = splitted_given_name[0].strip()
            last_name = splitted_given_name[0].strip()
        else:
            first_name = splitted_given_name[0].strip()
            last_name = splitted_given_name[1].strip()    
        user["attributes"]["firstName"] = first_name
        user["attributes"]["lastName"] = last_name
        ldap_json["users"].append(user)

    # -- Roles --
    for entry in range(1, len(roles["entries"])):
        role = {}
        role["dn"] = roles["entries"][entry]["dn"]
        role["attributes"] = {}
        for raw_attribute in roles["entries"][entry]["raw"]:
            if (raw_attribute == 'objectClass') or (raw_attribute == 'memberUid'):
                role["attributes"][raw_attribute] = roles["entries"][entry]["raw"][raw_attribute]
                # Memberships generation:
                if (raw_attribute == 'memberUid'):
                    for memberUid in roles["entries"][entry]["raw"]["memberUid"]:
                        membership = {}
                        membership["memberUid"] = memberUid
                        membership["role_cn"] = roles["entries"][entry]["raw"]["cn"][0]
                        membership["organization_dn"] = organization_dn
                        ldap_json["memberships"].append(membership)
            else:
                role["attributes"][raw_attribute] = roles["entries"][entry]["raw"][raw_attribute][0]                
        ldap_json["roles"].append(role)

    # -- Groups --
    for entry in range(1, len(groups["entries"])):
        group = {}
        group["dn"] = groups["entries"][entry]["dn"]
        group["attributes"] = {}
        for raw_attribute in groups["entries"][entry]["raw"]:
            if (raw_attribute == 'objectClass') or (raw_attribute == 'memberUid'):
                group["attributes"][raw_attribute] = groups["entries"][entry]["raw"][raw_attribute]
                # Include group common name (CN) in memberships:
                # Currently, only one group per user is included because of limitations with YARRRML (post processing of JSON output).
                if (raw_attribute == 'memberUid'):
                    for memberUid in groups["entries"][entry]["raw"]["memberUid"]:
                        for membership in ldap_json["memberships"]:
                            if membership["memberUid"] == memberUid:
                                membership["group_cn"] = groups["entries"][entry]["raw"]["cn"][0]
            else:
                group["attributes"][raw_attribute] = groups["entries"][entry]["raw"][raw_attribute][0]                
        ldap_json["groups"].append(group)

    # -- Organizations --
    for entry in range(0, len(orgs["entries"])):
        org = {}
        org["dn"] = orgs["entries"][entry]["dn"]
        org["attributes"] = {}
        for raw_attribute in orgs["entries"][entry]["raw"]:
            if (raw_attribute == 'objectClass'):
                org["attributes"][raw_attribute] = orgs["entries"][entry]["raw"][raw_attribute]
            else:
                org["attributes"][raw_attribute] = orgs["entries"][entry]["raw"][raw_attribute][0]                
        ldap_json["organizations"].append(org)
    
    logger.info("JSON object generated")
    
    return ldap_json

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application started")

    yield

    logger.info("Application finished")

## -- END DEFINITION OF AUXILIARY FUNCTIONS -- ##

## -- BEGIN MAIN CODE -- ##

app = FastAPI(
    lifespan=lifespan,
    title=__name__ + " - REST API",
    version=__version__
)

@app.get(path="/ldap.json", status_code=status.HTTP_200_OK)
async def get_ldap(request: Request) -> dict:
    logger.info("Received HTTP GET request from " + request.client.host + ":" + str(request.client.port) + " to /ldap.json")

    # Retrieve values related with LDAP from environmental variables.
    organization_dn = LDAP_ORGANIZATION_DN
    server_endpoint = LDAP_SERVER_ENDPOINT
    use_ssl = LDAP_USE_SSL
    user = LDAP_USER
    password = LDAP_PASSWORD
    max_retries = int(LDAP_CONN_MAX_RETRIES)
    timeout = int(LDAP_CONN_TIMEOUT)

    # Instantiate the representation of the LDAP server.
    server = Server(host=server_endpoint, use_ssl=use_ssl, get_info=ALL)

    # Try to establish the connection with the LDAP server.
    connection = establish_connection(server=server, user=user, password=password, max_retries=max_retries, timeout=timeout)

    # Retrieve LDAP information for users, roles, groups and organizations.
    users, roles, groups, orgs = retrieve_information(connection=connection, organization_dn=organization_dn)

    # Unbind the connection with the LDAP server.
    logger.info("Unbinding connection with the LDAP server...")
    connection.unbind()
    logger.info("Connection successfully unbinded")

    # Generate the JSON object with LDAP information.
    ldap_json = generate_json(users=users, roles=roles, groups=groups, orgs=orgs, organization_dn=organization_dn)

    logger.info("Returning JSON with LDAP data...")

    return ldap_json

## -- END MAIN CODE -- ##
