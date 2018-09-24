
class Factors(object):

    @staticmethod
    def mfa_providers():
        return [
            {
                'id': 'GoogleAuthenticator',
                'prompt': 'Google Authenticator',
                'factor_type': 'token:software:totp',
                'provider': 'GOOGLE'
            }, {
                'id': 'OktaVerify',
                'prompt': 'Okta Verify',
                'factor_type': 'token:software:totp',
                'provider': 'OKTA'
            }, {
                'id': 'Sms',
                'prompt': 'SMS text message',
                'factor_type': 'sms',
                'provider': 'OKTA'
            }, {
                'id': 'OktaPush',
                'prompt': 'Okta Verify with Push',
                'factor_type': 'push',
                'provider': 'OKTA'
            }
        ]
