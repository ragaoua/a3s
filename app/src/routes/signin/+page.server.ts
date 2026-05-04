import type { Actions } from './$types';
import { signIn } from '../../auth';

export const actions: Actions = { default: signIn };
