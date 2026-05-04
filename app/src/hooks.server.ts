import { redirect, type Handle } from '@sveltejs/kit';
import { sequence } from '@sveltejs/kit/hooks';
import { handle as authHandle } from './auth';

const PUBLIC_PATHS = ['/signin'];

const authorize: Handle = async ({ event, resolve }) => {
	if (event.url.pathname.startsWith('/auth/')) {
		return resolve(event);
	}

	const session = await event.locals.auth();
	if (!session?.user && !PUBLIC_PATHS.includes(event.url.pathname)) {
		throw redirect(303, '/signin');
	}

	return resolve(event);
};

export const handle = sequence(authHandle, authorize);
