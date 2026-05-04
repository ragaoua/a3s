import type { Session } from '@auth/sveltekit';

declare global {
	namespace App {
		// interface Error {}
		interface Locals {
			auth(): Promise<Session | null>;
		}
		interface PageData {
			session: Session | null;
		}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
