import { SvelteKitAuth } from '@auth/sveltekit';
import type { Handle } from '@sveltejs/kit';
import { getConfig } from '$lib/server/config';

const auth = getConfig().auth;

function buildAuth() {
	if (!auth.enabled) {
		const passthroughHandle: Handle = ({ event, resolve }) => {
			event.locals.auth = async () => null;
			return resolve(event);
		};
		const noopAction = async () => {};
		return {
			handle: passthroughHandle,
			signIn: noopAction,
			signOut: noopAction
		};
	}

	return SvelteKitAuth({
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
}

export const authEnabled = auth.enabled;
export const { handle, signIn, signOut } = buildAuth();
