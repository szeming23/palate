// In-memory stand-in for expo-secure-store, so tests never touch the device keystore.
const store = new Map<string, string>();

export const secureStoreMock = {
  getItemAsync: jest.fn(async (key: string) => store.get(key) ?? null),
  setItemAsync: jest.fn(async (key: string, value: string) => {
    store.set(key, value);
  }),
  reset: () => store.clear(),
};
