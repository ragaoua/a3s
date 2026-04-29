type PanelKinds = 'mcpServer' | 'skill' | 'subagent';

type OpenPanelState<TKind extends PanelKinds> =
	| { kind: TKind; mode: 'add' }
	| { kind: TKind; mode: 'edit'; index: number };
type TKindToOpenPanelState<TKind extends PanelKinds> = TKind extends PanelKinds
	? OpenPanelState<TKind>
	: never;
export type AnyOpenPanelState = TKindToOpenPanelState<PanelKinds>;

export type ClosedPanelState = { kind: 'closed' };

export type McpServerPanelState = OpenPanelState<'mcpServer'>;
export type SkillPanelState = OpenPanelState<'skill'>;
export type SubagentPanelState = OpenPanelState<'subagent'>;
