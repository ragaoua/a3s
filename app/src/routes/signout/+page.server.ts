import type { Actions } from './$types';
import { signOut } from '../../auth';

export const actions: Actions = { default: signOut };
