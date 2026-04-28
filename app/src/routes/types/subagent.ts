import { newOutboundAuthConfig, type OutboundAuthConfig } from './outboundAuthConfig';

export interface Subagent extends OutboundAuthConfig {
	name: string;
	url: string;
	type: SubagentType;
}

export function newSubagent(): Subagent {
	return {
		name: '',
		url: '',
		type: 'peer',
		...newOutboundAuthConfig()
	};
}

export const SUBAGENT_TYPE_OPTIONS = ['peer', 'delegate'] as const;

export type SubagentType = (typeof SUBAGENT_TYPE_OPTIONS)[number];

export const SUBAGENT_TYPE_LABELS: Record<SubagentType, string> = {
	peer: 'Peer',
	delegate: 'Delegate'
};
