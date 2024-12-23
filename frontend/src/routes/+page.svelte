<script lang="ts">
    import { onMount } from 'svelte';
    import Input from "$lib/components/ui/input/input.svelte";
    import Button from "$lib/components/ui/button/button.svelte";
    import Card from "$lib/components/ui/card/card.svelte";
    import CardContent from "$lib/components/ui/card/card-content.svelte";
    import CardHeader from "$lib/components/ui/card/card-header.svelte";
    import CardTitle from "$lib/components/ui/card/card-title.svelte";

    interface OrderItem {
        itemType: string;
        quantity: number;
    }

    interface OrderHistoryItem {
        id: number;
        actionType: string;
        items: OrderItem[];
        timestamp: string;
        display_message?: string;
    }

    interface Totals {
        burger: number;
        fries: number;
        drink: number;
    }

    let message = '';
    let history: OrderHistoryItem[] = [];
    let totals: Totals = { burger: 0, fries: 0, drink: 0 };
    let loading = false;
    let error = '';

    async function fetchOrders() {
        try {
            const [ordersRes, totalsRes] = await Promise.all([
                fetch('http://localhost:8000/orders'),
                fetch('http://localhost:8000/totals')
            ]);
            
            if (!ordersRes.ok || !totalsRes.ok) {
                throw new Error('Failed to fetch data from server');
            }
            
            const historyData = await ordersRes.json();
            history = historyData.map((item: any) => ({
                ...item,
                actionType: item.action_type,
                items: item.items.map((item: any) => ({
                    itemType: item.item_type,
                    quantity: item.quantity
                })),
                display_message: item.display_message
            }));
            totals = await totalsRes.json();
        } catch (err) {
            console.error('Error fetching data:', err);
            error = err instanceof Error ? err.message : 'Failed to fetch orders';
        }
    }

    function handleSubmit(event: Event) {
        console.log('Form submitted');
        event.preventDefault();
        if (!message.trim()) {
            console.log('Message is empty');
            return;
        }
        processOrder();
    }

    async function processOrder() {
        console.log('Processing order with message:', message);
        loading = true;
        error = '';
        
        try {
            console.log('Sending request to backend...');
            const response = await fetch('http://localhost:8000/process-order', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message }),
            });
            
            console.log('Response received:', response.status);
            const data = await response.json();
            console.log('Response data:', data);
            
            if (!response.ok) {
                throw new Error(data.detail || 'Failed to process order');
            }
            
            if (data.status === 'error') {
                error = data.display_message || data.message;
                return;
            }
            
            history = data.history.map((item: any) => ({
                ...item,
                actionType: item.action_type,
                items: item.items.map((item: any) => ({
                    itemType: item.item_type,
                    quantity: item.quantity
                })),
                display_message: item.display_message
            }));
            totals = data.totals;
            message = '';
        } catch (err) {
            console.error('Error processing order:', err);
            error = err instanceof Error ? err.message : 'Failed to process order';
        } finally {
            loading = false;
        }
    }

    onMount(fetchOrders);
</script>

<div class="container mx-auto p-4 max-w-4xl">
    <div class="grid grid-cols-3 gap-4 mb-8">
        <Card>
            <CardHeader>
                <CardTitle>Total # of burgers</CardTitle>
            </CardHeader>
            <CardContent>
                <p class="text-4xl font-bold">{totals.burger}</p>
            </CardContent>
        </Card>
        
        <Card>
            <CardHeader>
                <CardTitle>Total # of fries</CardTitle>
            </CardHeader>
            <CardContent>
                <p class="text-4xl font-bold">{totals.fries}</p>
            </CardContent>
        </Card>
        
        <Card>
            <CardHeader>
                <CardTitle>Total # of drinks</CardTitle>
            </CardHeader>
            <CardContent>
                <p class="text-4xl font-bold">{totals.drink}</p>
            </CardContent>
        </Card>
    </div>

    <Card className="mb-8">
        <CardContent className="pt-6">
            <form on:submit={handleSubmit} class="flex gap-2">
                <Input
                    placeholder="Ex: 'I would like one burger and an order of fries'"
                    bind:value={message}
                    disabled={loading}
                    className="flex-1"
                />
                <Button type="submit" disabled={loading}>
                    {loading ? 'Processing...' : 'Run'}
                </Button>
            </form>
            {#if error}
                <div class="mt-2 p-3 bg-red-50 border border-red-200 rounded-md">
                    <p class="text-red-600">{error}</p>
                </div>
            {/if}
        </CardContent>
    </Card>

    <Card>
        <CardHeader>
            <CardTitle>Order History</CardTitle>
        </CardHeader>
        <CardContent>
            {#if history.length === 0}
                <p class="text-gray-500">No orders yet</p>
            {:else}
                <div class="space-y-4">
                    {#each history as item}
                        <div class="flex justify-between items-center p-4 rounded-lg {item.actionType === 'cancel' ? 'bg-red-50 border border-red-200' : 'bg-gray-50'}">
                            <div class="flex flex-col">
                                <span class="font-medium">
                                    {#if item.actionType === 'cancel'}
                                        <span class="text-red-600">#{item.id} - Cancelled</span>
                                    {:else}
                                        #{item.id} - {item.actionType}
                                    {/if}
                                </span>
                                <span class="text-sm text-gray-500">{new Date(item.timestamp).toLocaleString()}</span>
                            </div>
                            <div class="flex flex-col items-end">
                                {#if item.actionType === 'cancel' && item.display_message}
                                    <span class="font-medium text-red-600">
                                        {item.display_message}
                                    </span>
                                {:else}
                                    <span>
                                        {item.items.map(item => `${item.quantity} ${item.itemType}`).join(', ')}
                                    </span>
                                {/if}
                            </div>
                        </div>
                    {/each}
                </div>
            {/if}
        </CardContent>
    </Card>
</div>
