<template>
  <div id="app">
    <header>
      <h1>MaiCore-Initiate WebUI</h1>
      <nav>
        <router-link to="/">数据仪表盘</router-link>
        <router-link to="/instances">实例管理</router-link>
        <router-link to="/settings">程序设置</router-link>
      </nav>
    </header>
    <main>
      <router-view />
    </main>
  </div>
</template>

<script setup>
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
}

header {
  background-color: #f8f9fa;
  padding: 1rem;
  border-bottom: 1px solid #dee2e6;
  text-align: center;
}

nav {
  margin-top: 1rem;
}

nav a {
  font-weight: bold;
  color: #2c3e50;
  text-decoration: none;
  margin: 0 1rem;
  padding: 0.5rem 1rem;
  border-radius: 4px;
}

nav a.router-link-exact-active {
  color: #fff;
  background-color: #007bff;
}

main {
  padding: 2rem;
  text-align: center;
}
</style>