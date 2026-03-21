<script lang="ts">

  let {
    label,
    id,
    name,
    value = $bindable(''),
    type = 'text',
    placeholder = '',
    required = false,
    isTextarea = false,
  }: {
    label?: string,
    id: string,
    name: string,
    value: string,
    type?: 'text' | 'url' | 'password' | 'email',
    placeholder?: string,
    required?: boolean,
    isTextarea?: boolean,
  } = $props();

	const fieldClass =
		'w-full rounded-lg border border-neutral-700 bg-black/50 px-3 py-2 text-sm text-neutral-100 outline-none transition placeholder:text-neutral-500 focus:border-neutral-300';
</script>

<div class="space-y-2 w-full">
  {#if label}
    <label for={id} class="text-sm font-medium">{label}</label>
  {/if}

	{#if isTextarea}
		<textarea
			{id}
			{name}
			rows={3}
			bind:value
			{placeholder}
			{required}
			class={fieldClass}
		></textarea>
	{:else}
		<input
      {id}
			{name}
			{type}
			bind:value
			{placeholder}
			{required}
			class={fieldClass}
		/>
	{/if}
</div>
