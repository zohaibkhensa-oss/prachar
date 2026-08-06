// Type declarations for Google Identity Services and Apple Sign-In JS

interface GoogleCredentialResponse {
  credential: string;
  select_by?: string;
}

interface GoogleAccountsId {
  initialize(config: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void;
    auto_select?: boolean;
    cancel_on_tap_outside?: boolean;
  }): void;
  prompt(): void;
  renderButton(parent: HTMLElement, options: Record<string, unknown>): void;
  disableAutoSelect(): void;
}

interface GoogleNamespace {
  accounts: {
    id: GoogleAccountsId;
  };
}

interface AppleIDName {
  firstName?: string;
  lastName?: string;
}

interface AppleIDUser {
  name?: AppleIDName;
  email?: string;
}

interface AppleIDAuthResponse {
  authorization: {
    code: string;
    id_token: string;
    state?: string;
  };
  user?: AppleIDUser;
}

// Convenience: the actual response shape from AppleID.auth.signIn()
// Some SDK versions flatten authorization to top level
type AppleIDSignInResponse = AppleIDAuthResponse & {
  id_token?: string;
  code?: string;
  state?: string;
  user?: AppleIDUser;
};

interface AppleIDAuthConfig {
  clientId: string;
  scope: string;
  redirectURI: string;
  usePopup?: boolean;
  state?: string;
  nonce?: string;
}

interface AppleIDAuth {
  init(config: AppleIDAuthConfig): void;
  signIn(): Promise<AppleIDSignInResponse>;
}

interface AppleIDNamespace {
  auth: AppleIDAuth;
}

interface Window {
  google?: GoogleNamespace;
  AppleID?: AppleIDNamespace;
}
