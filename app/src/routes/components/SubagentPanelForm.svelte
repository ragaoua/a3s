<script lang="ts">
	import { SUBAGENT_TYPE_LABELS, SUBAGENT_TYPE_OPTIONS, type Subagent } from '../types/subagent';
	import FormField from './FormField.svelte';
	import OutboundAuthConfigForm from './OutboundAuthConfigForm.svelte';

	let {
		subagentDraft = $bindable(),
		agentAuthMismatch
	}: {
		subagentDraft: Subagent;
		agentAuthMismatch: boolean;
	} = $props();
</script>

<FormField
	label="Subagent URL"
	id="subagent-draft"
	name="subagentDraft"
	type="url"
	bind:value={subagentDraft.url}
	placeholder="https://example-subagent.com"
	required
/>

<div class="w-full space-y-2">
	<label for="subagent-type" class="text-sm font-medium">Type</label>
	<select
		id="subagent-type"
		name="subagentTypeDraft"
		bind:value={subagentDraft.type}
		class="w-full rounded-lg border border-neutral-700 bg-black/50 px-3 py-2 text-sm text-neutral-100 transition outline-none focus:border-neutral-300"
	>
		{#each SUBAGENT_TYPE_OPTIONS as type (type)}
			<option value={type}>{SUBAGENT_TYPE_LABELS[type]}</option>
		{/each}
	</select>
</div>

<OutboundAuthConfigForm
	bind:auth={subagentDraft}
	subjectLabel="subagent"
	idPrefix="subagent"
	namePrefix="subagent"
	{agentAuthMismatch}
/>
