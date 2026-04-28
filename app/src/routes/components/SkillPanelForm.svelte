<script lang="ts">
	import type { Skill } from '../types/skill';
	import FormField from './FormField.svelte';

	let {
		skillDraft = $bindable()
	}: {
		skillDraft: Skill;
	} = $props();
</script>

<FormField
	label="Name"
	id="skill-name"
	name="skillName"
	bind:value={skillDraft.name}
	placeholder="lowercase-with-hyphens (max 64 chars)"
	pattern="[a-z0-9]+(-[a-z0-9]+)*"
	maxlength={64}
	title="Lowercase letters, numbers, and hyphens only. Must not start or end with a hyphen."
	required
/>

<FormField
	label="Description"
	id="skill-description"
	name="skillDescription"
	bind:value={skillDraft.description}
	placeholder="What this skill does (max 1024 chars)."
	maxlength={1024}
	required
/>

<FormField
	label="Content"
	id="skill-content"
	name="skillContent"
	bind:value={skillDraft.content}
	placeholder="The skill instructions, prompt, or body."
	isTextarea
	required
/>
