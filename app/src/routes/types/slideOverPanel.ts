type IndexedPanelKinds = 'mcpServer' | 'skill' | 'subagent';
type SingletonPanelKinds = 'oauth2Jwt' | 'oauth2Introspection';
type PanelKinds = IndexedPanelKinds | SingletonPanelKinds;

type IndexedOpenPanelState<TKind extends IndexedPanelKinds> =
	| { kind: TKind; mode: 'add' }
	| { kind: TKind; mode: 'edit'; index: number };
type SingletonOpenPanelState<TKind extends SingletonPanelKinds> = { kind: TKind };

type OpenPanelState<TKind extends PanelKinds> = TKind extends IndexedPanelKinds
	? IndexedOpenPanelState<TKind>
	: TKind extends SingletonPanelKinds
		? SingletonOpenPanelState<TKind>
		: never;
type TKindToOpenPanelState<TKind extends PanelKinds> = TKind extends PanelKinds
	? OpenPanelState<TKind>
	: never;
export type AnyOpenPanelState = TKindToOpenPanelState<PanelKinds>;

export type ClosedPanelState = { kind: 'closed' };

export type McpServerPanelState = IndexedOpenPanelState<'mcpServer'>;
export type SkillPanelState = IndexedOpenPanelState<'skill'>;
export type SubagentPanelState = IndexedOpenPanelState<'subagent'>;
export type Oauth2JwtPanelState = SingletonOpenPanelState<'oauth2Jwt'>;
export type Oauth2IntrospectionPanelState = SingletonOpenPanelState<'oauth2Introspection'>;
