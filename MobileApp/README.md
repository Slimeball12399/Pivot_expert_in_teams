# MobileApp

Expo SDK 57 app in plain JavaScript, using **Expo Router** for navigation.

## Run

```bash
npm install
npx expo start
```

The app targets **iOS and Android only**. Web is disabled with `"platforms": ["ios", "android"]` in `app.json`.

## Project structure

```
assets/
├── fonts/                  # Custom font files (empty for now)
├── images/                 # App icon, splash and other images
└── styles/
    └── colors.js           # Color palette used by the theme
src/
├── app/                    # Routes: every file here is a screen (Expo Router)
│   ├── _layout.js          # Root layout: AppProviders + navigator (replaces App.js)
│   └── index.js            # Home screen, the "/" route, opens on launch
└── providers/
    ├── AppProviders.js     # Composes all app-wide providers in one wrapper
    ├── ThemeProvider.js    # App theme (colors, sizes, styles) -> useTheme()
    └── EmptyProvider.js    # Placeholder provider for future shared state -> useEmpty()
```

Keep non-route code (components, providers, utils) **outside** `src/app/`. Any file inside it becomes a screen.

### Adding a screen

1. Create `src/app/settings.js` that exports a component as `default`.
2. Navigate to it:

```js
import { Link, router } from 'expo-router';

<Link href="/settings">Settings</Link>
// or
router.push('/settings');
```

3. Optional: set its header title in `src/app/_layout.js`:

```js
<Stack.Screen name="settings" options={{ title: 'Settings' }} />
```

### Using the theme

```js
import { useTheme } from '../providers/ThemeProvider';

const { theme } = useTheme();
<Text style={theme.styles.text.title}>Hello</Text>
<View style={{ backgroundColor: theme.colors.primary }} />
```

`ThemeProvider` also passes the colors to the navigator (via Expo Router's `ThemeProvider`) so headers and screen backgrounds match the app.

### Adding a provider

Create it in `src/providers/` and add it to `src/providers/AppProviders.js`, next to `EmptyProvider`. The root layout does not need to change.

---

## Expo Router vs React Navigation

Expo Router is built on top of React Navigation. Both give the same native screens, stacks, tabs and transitions. The difference is how screens are declared and how you move between them.

### Which one is official?

| Source | Recommends |
|---|---|
| [Expo documentation](https://docs.expo.dev/router/introduction/) | **Expo Router**: "if you are building a new app, we recommend using Expo Router". It is also used by the official `create-expo-app` template. |
| [React Native documentation](https://reactnative.dev/docs/navigation) | **React Navigation**, the general navigation library for React Native. |

This project is built on Expo, so it follows Expo's recommendation: **Expo Router**. Because Expo Router is built on React Navigation, it is consistent with the React Native recommendation as well.

### Declaring screens

**React Navigation**: every screen is registered by hand in one file.

```js
// App.js / Navigation.js
<NavigationContainer>
  <Stack.Navigator initialRouteName="Home">
    <Stack.Screen name="Home" component={HomeScreen} />
    <Stack.Screen name="Settings" component={SettingsScreen} />
  </Stack.Navigator>
</NavigationContainer>
```

**Expo Router**: the file structure is the navigation. No registration needed.

```
src/app/_layout.js    -> the <Stack> navigator (the role of Navigation.js)
src/app/index.js      -> Home, shown first
src/app/settings.js   -> /settings
```

### Side-by-side

| | React Navigation | Expo Router |
|---|---|---|
| Entry point | `index.js` -> `registerRootComponent(App)` | `"main": "expo-router/entry"` in `package.json` |
| Root component | `App.js` | `src/app/_layout.js` |
| Defining screens | Listed manually in a navigator | One file per screen in `src/app/` |
| First screen | `initialRouteName="Home"` | `src/app/index.js` |
| Navigate | `navigation.navigate('Settings')` | `router.push('/settings')` or `<Link href="/settings">` |
| Pass parameters | `navigate('Event', { id: 5 })` -> `route.params.id` | `/event/5` with file `event/[id].js` -> `useLocalSearchParams()` |
| Access navigation | `navigation` prop passed to screens | Import `router` anywhere |
| Deep links (`mobileapp://settings`) | Configured manually | Automatic, every file has a URL |
| Web support | Possible with extra setup | Built in, with real URLs |
| Large apps | One navigation file keeps growing | Each folder can have its own small `_layout.js` |

### How the original template maps to this project

| Original Expo template | This project |
|---|---|
| `index.js` calls `registerRootComponent(App)` | `expo-router/entry` does this automatically |
| `App.js`, the root component | `src/app/_layout.js` |
| The content inside `App.js` | `src/app/index.js` |
| `<StatusBar>` in `App.js` | `<StatusBar>` in `src/app/_layout.js` |

### References

- Expo Router introduction: https://docs.expo.dev/router/introduction/
- Expo Router installation: https://docs.expo.dev/router/installation/
- Stack navigator: https://docs.expo.dev/router/advanced/stack/
- React Native navigation: https://reactnative.dev/docs/navigation
