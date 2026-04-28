export interface Skill {
	name: string;
	description: string;
	content: string;
}

export function newSkill(): Skill {
	return {
		name: '',
		description: '',
		content: ''
	};
}
