export class AuthModel {
  accessToken: string;
  refreshToken: string;
  authenticateResult: boolean;

  setAuth(auth: AuthModel) {
    this.accessToken = auth.accessToken;
    this.refreshToken = auth.refreshToken;
    this.authenticateResult = auth.authenticateResult;
  }
}
