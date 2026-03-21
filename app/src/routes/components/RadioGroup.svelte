<script lang='ts'>
  let {
    name,
    group = $bindable(""),
    choices
  }: {
    name: string,
    group: string,
    choices: { value: string, label: string }[]
  } = $props();

  const inputClass =
    "flex cursor-pointer items-center gap-2 rounded-lg border border-neutral-700 bg-black/45 px-3 py-2 text-sm text-neutral-200"
</script>

<div class="flex gap-3">
  {#each choices as choice (choice)}
    <label class={inputClass}>
      <input class="accent-neutral-300" type="radio" {name} value={choice.value} bind:group />
      <span>{choice.label}</span>
    </label>
  {/each}
</div>
