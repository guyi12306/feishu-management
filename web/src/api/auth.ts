import client from "./client";

export interface User {
  id: number;
  username: string;
  display_name: string | null;
}

export const authApi = {
  async login(username: string, password: string): Promise<User> {
    const { data } = await client.post("/login", { username, password });
    return data.user;
  },
  async logout(): Promise<void> {
    await client.post("/logout");
  },
  async me(): Promise<User | null> {
    try {
      const { data } = await client.get("/me");
      return data.user;
    } catch {
      return null;
    }
  },
  async changePassword(old_password: string, new_password: string): Promise<void> {
    await client.post("/change-password", { old_password, new_password });
  },
};


