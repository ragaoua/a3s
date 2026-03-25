export type Auth =
	| {
			type: 'none' | 'apiKey';
	  }
	| {
			type: 'oauth2';
			oauth2IssuerUrl: string;
			oauth2Audience?: string;
			oauth2JwksUrl?: string;
	  };
