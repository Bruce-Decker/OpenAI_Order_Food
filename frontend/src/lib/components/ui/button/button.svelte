<script lang="ts">
	import { Button as ButtonPrimitive } from "bits-ui";
	import { cn } from "$lib/utils";
	import type { Button as ButtonPrimitiveType } from "bits-ui";

	type $$Props = ButtonPrimitiveType.Props;

	let className: $$Props["class"] = undefined;
	export { className as class };
</script>

<ButtonPrimitive.Root
	class={cn(
		"inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ring-offset-background",
		"bg-primary text-primary-foreground hover:bg-primary/90",
		"h-10 px-4 py-2",
		className
	)}
	{...$$restProps}
>
	<slot />
</ButtonPrimitive.Root>
