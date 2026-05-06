<template>
  <nav>
    <span class="brand">StockVision</span>
    <RouterLink to="/users">LINE 成員</RouterLink>
    <RouterLink to="/performance">預測比對</RouterLink>
  </nav>
  <main>
    <RouterView />
  </main>
</template>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f7fa; color: #333; }
nav { background: #1a1a2e; padding: 0 24px; display: flex; align-items: center; gap: 24px; height: 56px; }
nav .brand { color: #fff; font-weight: 700; font-size: 16px; margin-right: 16px; }
nav a { color: #ccc; text-decoration: none; font-size: 14px; padding: 8px 0; border-bottom: 2px solid transparent; }
nav a:hover, nav a.router-link-active { color: #fff; border-bottom-color: #4a90d9; }
main { max-width: 1200px; margin: 32px auto; padding: 0 24px; }
</style>
