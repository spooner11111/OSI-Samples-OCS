"""This script performs Authorization Code + PKCE Authentication against OSIsoft Cloud Services"""

# Disable pylint warnings:
# Allow catching general exception Exception (broad-except)
# pylint: disable=W0703
# Allow more than 15 local variables (too-many-locals)
# pylint: disable=R0914
# Allow more than 50 statements (too-many-statements)
# pylint: disable=R0915

import base64
import configparser
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import secrets
import time
from urllib.parse import urlparse, parse_qs
import webbrowser

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def main(test=False):
    """Main sample script
    Performs Authorization Code + PKCE Authentication against OSIsoft Cloud Services.
    If test=True, will use Selenium to perform browser authentication automatically.
    """

    try:
        config = configparser.ConfigParser()
        config.read('config.ini')

        resource = config.get('Configuration', 'Resource')
        tenant_id = config.get('Configuration', 'TenantId')
        client_id = config.get('Configuration', 'ClientId')

        redirect_uri = 'http://localhost:5004/callback.html'
        scope = 'openid ocsapi'

        # Set up PKCE Verifier and Code Challenge
        verifier = base64.urlsafe_b64encode(
            secrets.token_bytes(32)).rstrip(b'=')
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier).digest()).rstrip(b'=')

        # Get OAuth endpoint configuration
        print()
        print('Step 1: Get OAuth endpoint configuration...')
        endpoint = json.loads(requests.get(
            resource + '/identity/.well-known/openid-configuration').content)
        auth_endpoint = endpoint.get('authorization_endpoint')
        token_endpoint = endpoint.get('token_endpoint')

        # Set up request handler for web browser login
        print()
        print('Step 2: Set up server to process authorization response...')

        class RequestHandler(BaseHTTPRequestHandler):
            """Handles authentication redirect uri and extracts authorization code from URL"""
            code = ''

            # pylint: disable=C0103
            def do_GET(self):
                """Handles GET request against this temporary local server"""
                # Parse out authorization code from query string in request
                RequestHandler.code = parse_qs(
                    urlparse(self.path).query)['code'][0]

                # Write response
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(
                    '<h1>You can now return to the application.</h1>'.encode())

        # Set up server for web browser login
        server = HTTPServer(('', 5004), RequestHandler)

        # Open web browser against authorization endpoint
        print()
        print('Step 3: Authorize the user...')
        auth_url = auth_endpoint + \
            '?response_type=code&code_challenge=' + challenge.decode() + \
            '&code_challenge_method=S256&client_id=' + client_id + \
            '&redirect_uri=' + redirect_uri + \
            '&scope=' + scope + \
            '&acr_values=tenant:' + tenant_id

        if test:
            # Get Config
            username = config.get('Test', 'Username')
            password = config.get('Test', 'Password')

            # Open Chrome Webdriver, go to Auth page
            print()
            print('Selenium 1: Open Chrome WebDriver')
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            browser = webdriver.Chrome(options=chrome_options)
            browser.get(auth_url)
            time.sleep(2)

            # Use Personal Account (Must be enabled on Tenant)
            print()
            print('Selenium 2: Choose Personal Account')
            browser.find_element_by_xpath(
                xpath='descendant::a[@title="Personal Account"]').click()
            time.sleep(2)

            # Enter Username and submit
            print()
            print('Selenium 3: Enter Username')
            browser.find_element_by_xpath(
                '//*[@id="i0116"]').send_keys(username)
            browser.find_element_by_xpath('//*[@id="idSIButton9"]').click()
            time.sleep(2)

            # Enter Password and submit
            print()
            print('Selenium 4: Enter Password')
            browser.find_element_by_xpath(
                '//*[@id="i0118"]').send_keys(password)
            elem = browser.find_element_by_xpath('//*[@id="idSIButton9"]')
            try:
                browser.set_page_load_timeout(2)
                elem.click()
            except Exception:
                print('Ignore time out, start the server...')
        else:
            # Open user default web browser at Auth page
            webbrowser.open(auth_url)

        # Wait for response in browser
        print()
        print('Step 4: Set server to handle one request...')
        server.handle_request()

        # Use authorization code to get bearer token
        print()
        print('Step 5: Get a token using the authorization code...')
        token = requests.post(token_endpoint, [
            ('grant_type', 'authorization_code'),
            ('client_id', client_id),
            ('code_verifier', verifier),
            ('code', RequestHandler.code),
            ('redirect_uri', redirect_uri)])

        token = json.loads(token.content).get('access_token')
        print()
        print('Step 6: Read the Access Token:')
        print(token)

        if test:
            assert token, "Failed to obtain access token"

        print()
        print('Complete!')
    except Exception as error:
        print()
        msg = "Encountered Error: {error}".format(error=error)
        print(msg)
        assert False, msg


if __name__ == "__main__":
    main()