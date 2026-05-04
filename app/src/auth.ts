import { SvelteKitAuth } from '@auth/sveltekit';
import { getConfig } from '$lib/server/config';

const auth = getConfig().auth;

export const { handle, signIn, signOut } = SvelteKitAuth({
	secret: auth.secret,
	trustHost: true,
	providers: [
		{
			id: 'oidc',
			name: 'OIDC',
			type: 'oidc',
			issuer: auth.issuerUrl,
			clientId: auth.clientId,
			clientSecret: auth.clientSecret,
			...(auth.publicClient && { client: { token_endpoint_auth_method: 'none' } })
		}
	],
	pages: {
		signIn: '/signin'
	}
});
