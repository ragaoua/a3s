import { SvelteKitAuth } from '@auth/sveltekit';
import type { Handle } from '@sveltejs/kit';
import { getConfig } from '$lib/server/config';

function buildAuth() {
	const auth = getConfig().auth;
	if (!auth.enabled) {
		return {
			handle: (({ event, resolve }) => {
				event.locals.auth = async () => null;
				return resolve(event);
			}) satisfies Handle,
			signIn: async () => {},
			signOut: async () => {},
			enabled: false
		};
	}

	return {
		...SvelteKitAuth({
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
		}),
		enabled: true
	};
}

let auth: ReturnType<typeof buildAuth>;
function getAuth() {
	if (!auth) auth = buildAuth();
	return auth;
}

export const handle: Handle = (input) => getAuth().handle(input);
export const authEnabled = () => getAuth().enabled;
export const signIn: typeof auth.signIn = (...args) => getAuth().signIn(...args);
export const signOut: typeof auth.signOut = (...args) => getAuth().signOut(...args);
