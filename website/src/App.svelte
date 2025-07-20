<script lang="ts">
  // import type { RouteConfig } from "@mateothegreat/svelte5-router";
  // import { Router } from "@mateothegreat/svelte5-router";
  // import Home from "./routes/Home.svelte";
  import SavedChat from "./routes/SavedChat.svelte";

  // const routes: RouteConfig[] = [
  //   { component: Home },
  //   {
  //     path: "/saved-chat/(?<channelId>[0-9]+)/(?<messageId>[0-9]+)",
  //     component: SavedChat,
  //   },
  // ];
</script>

<main>
  <SavedChat />
  <!-- <Router {routes} /> -->
</main>
