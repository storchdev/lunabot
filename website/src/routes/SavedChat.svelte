<script lang="ts">
    import { onMount } from "svelte";
    import axios from "axios";

    document.title = "Saved chat";

    type Message = Record<string, any>;
    let messages: Array<Message> = $state([]);
    // let { route } = $props();

    // const channelId = route.result.path.params.channelId;
    // const messageId = route.result.path.params.messageId;

    onMount(() => {
        const params = new URLSearchParams(window.location.search);
        const channelId = params.get("channelId");
        const messageId = params.get("messageId");

        axios
            .get(
                `https://hudsonshi.com/lunabot/api/saved-chat/${channelId}/${messageId}`,
            )
            .then((resp) => {
                messages = resp.data;
            })
            .catch((e) => {
                alert(`Error: ${e.response.data.error}`);
            });
    });

    function unixToLocal(timestamp: number): string {
        const date: Date = new Date(timestamp * 1000); // Convert seconds to milliseconds

        const year: number = date.getFullYear();
        const month: string = String(date.getMonth() + 1).padStart(2, "0"); // Months are 0-indexed
        const day: string = String(date.getDate()).padStart(2, "0");
        const hours: string = String(date.getHours()).padStart(2, "0");
        const minutes: string = String(date.getMinutes()).padStart(2, "0");
        const seconds: string = String(date.getSeconds()).padStart(2, "0");

        return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    }

    async function handleCopyID(e: MouseEvent, m: Message) {
        e.preventDefault();
        await navigator.clipboard.writeText(m.author.id.toString());
        alert(`Copied ID for ${m.author.display_name}`);
    }
</script>

<main class="m-8 flex flex-col gap-8 text-white">
    {#each messages as message}
        <div class="flex gap-8 items-center">
            <div class="flex gap-4">
                <img
                    class="min-w-10 max-w-10 min-h-10 max-h-10 rounded-[999px]"
                    src={message.author.avatar_url}
                    alt={message.author.display_name}
                    oncontextmenu={(e) => handleCopyID(e, message)}
                />
                <div class="flex flex-col gap-0">
                    <div class="flex gap-2 items-center">
                        <p class="text-[#cab7ff] font-bold">
                            {message.author.display_name}
                        </p>
                        <p class="text-gray-500 text-sm">
                            {unixToLocal(message.timestamp)}
                        </p>
                    </div>
                    <p>
                        {message.content}
                    </p>
                </div>
            </div>
        </div>
    {/each}
</main>
