#!/usr/bin/env python3

import requests,json,re
import logging as log

class Glowmarkt:
    URL='https://api.glowmarkt.com/api/v0-1/' # The API URL
    token = None
    headers = {
        'token': None,
        'applicationId': 'b0f1b774-a586-4f72-9edd-27ead8aa7a8d'
    }
    jwt = re.compile('^([a-zA-Z0-9]+\.){2}([a-zA-Z0-9]+)$')
    
    def authorise(self, u=None, p=None, t=None, appId=None):
        endpoint = self.URL + 'auth'
        reauth = False
        data = None
        
        if not (u or p or t) and self.headers.token:
            log.info('{}.authorise(): reauthorising existing token'.format(self.__name__))
            reauth = True
        elif t:
            assert jwt.match(t), 'token (t) must be a valid JSON Web Token (JWT)'
            log.info('{}.authorise(): reauthorising provided token'.format(self.__name__))
            self.headers.token = t
            reauth = True
        else:
            assert u.len() > 0 and p.len() > 0, 'Username (u) and password (p) must be non-empty strings'
            log.info('{}.authorise(): authorising user {}'.format(self.__name__,u))
            data = {'username': u, 'password': p}
        
        if appId:
            assert appId.len() > 0, 'appId must be a non-empty string'
            self.headers.applicationId = appId
        
        try:
            if reauth:
                response = requests.get(endpoint,headers=self.headers)
            else:
                response = requests.post(endpoint,headers=self.headers,json=data)
            response.raise_for_status()
        except (ConnectionErrror, HTTPError, Timeout, TooManyRedirects) as err:
            if err.response and int(err.response) < 500:
                log.error('{}.authorise(): HTTP Error {}'.format(__name__,err.response))
                raise
            else:
                log.error('{}.authorise(): server error - aborting!'.format(__name__,err.response))
                sys.exit()
        
        self.token = json.load(response.json())
        self.headers.token = self.token.token
        return True
    
    def __init__(self, u=None, p=None, t=None):
        self.authorise(u,p,t)
        return self

if __name__ == "__main__":
    import sys,argparse,pickle
    from pathlib import Path
    from xdg import xdg_config_home
    from getpass import getpass
    
    config = xdg_config_home() / 'glowmarkt.conf'
    gm = None
    
    p = argparse.ArgumentParser(description='Query the Glowmarkt API')
    p.add_argument('-v','--verbose',action='store_const',const=True,help='increase output verbosity')
    p.add_argument('-c','--config',type=str,nargs='?',help='load configuration from file CONFIG (defaults to {}'.format(config),default=None,const=str(config))
    p.add_argument('-u','--user',type=str,help='account username')
    p.add_argument('-t','--token',type=str,help='provide the token value from a previous authorisation')
    args = p.parse_args()
    
    if not (args.config or args.user or args.token):
        p.error('At least one option required: --config, --token or --user')
    
    if args.verbose:
        log.basicConfig(format="%(levelname)s: %(message)s", level=log.DEBUG)
        log.info("Verbose output.")
    else:
        log.basicConfig(format="%(levelname)s: %(message)s")
    
    log.info('Called with arguments: ' + dir(args))
    
    if args.config == None: config = None
    else:
        # Check and load the congifuration file
        config = Path(args.config)
        log.info('Configuration file is {}'.format(config))
        try:
            if config.is_file():
                log.info('Found {}'.format(config))
                if config.stat().st_size == 0:
                    log.info('Configuration file empty; ignoring')
                else:
                    with config.open('rb') as f:
                        gm = pickle.load(f)
                    if gm:
                        log.info('Object loaded from configuration file')
            else:
                config.touch()
                log.info('Created new configuration file')
        except Exception as err:
            log.error('Configuration file ({}) error: {}'.format(config, err))
            sys.exit(1)
    
    # Instantiate or update the gm object from user provided details
    if args.token:
        log.info('Token provided: checking validity')
        if gm:
            gm.authorise(t=args.token)
        else:
            gm = Glowmarkt(t=args.token)
        log.info('Token validated! Ready to query API')
    if args.user:
        log.info('Username {} provided: getting password'.format(args.user))
        if gm.token:
            gm.token = None
            log.info('Stored token cleared; reauthorising with username and password')
        for i in range(3):
            pwd = getpass('Password for {}:'.format(args.user))
            try:
                if gm:
                    gm.authorise(u=args.user,p=pwd)
                else:
                    gm = Glowmarket(u=args.user,p=pwd)
            except HTTPError:
                log.error('Password not accepted for user {}.'.format(args.user))
                print('Username or password not accepted. Try again?')
                continue
            else:
                log.info('User {} authorised!'.format(args.user))
            

    # Save configuration and clean up
    if config:
        if gm:
            try:
                with config.open('wb') as f:
                    pickle.dump(gm,f,pickle.HIGHEST_PROTOCOL)
            except Exception as err:
                print('Couldn\'t save configuration to file ' + str(config) + ': ' + str(err))
        if config.is_file() and config.stat().st_size == 0:
            print('Removing empty configuration file ' + str(config))
            try:
                config.unlink()
            except Exception as err:
                print('Error deleting empty configuration file ' + str(config) + ': ' + str(err))