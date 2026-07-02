namespace UserManagement.Model
{
    public class UserLoginResponse
    {
        // <summary>Gets or sets a value indicating whether [authenticate result].</summary>
        /// <value>
        ///   <c>true</c> if [authenticate result]; otherwise, <c>false</c>.</value>
        public bool AuthenticateResult { get; set; }

        /// <summary>Gets or sets the authentication token.</summary>
        /// <value>The authentication token.</value>
        public string AccessToken { get; set; }

        /// <summary>Gets or sets the access token expire date.</summary>
        /// <value>The access token expire date.</value>
        //public DateTime AccessTokenExpireDate { get; set; }

        /// <summary>Gets or sets the refresh token.</summary>
        /// <value>The refresh token.</value>
        public string RefreshToken { get; set; }

        /// <summary>Gets or sets the refresh token expire date.</summary>
        /// <value>The refresh token expire date.</value>
        //public DateTime RefreshTokenExpireDate { get; set; }


    }
}
