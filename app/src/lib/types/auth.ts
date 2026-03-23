export type Auth =
	| {
			type: 'none' | 'apiKey';
	  }
	| {
			type: 'oauth2';
			oauth2IssuerUrl: string;
			oauth2JwksUrl?: string;
	  };
