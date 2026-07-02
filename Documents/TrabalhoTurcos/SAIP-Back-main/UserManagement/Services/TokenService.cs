using Microsoft.IdentityModel.Tokens;
using Newtonsoft.Json;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using UserManagement.Interfaces;
using UserManagement.Model;

namespace UserManagement.Services
{
    public class TokenService : ITokenService
    {
        readonly IConfiguration configuration;

        public TokenService(IConfiguration configuration)
        {
            this.configuration = configuration;

        }

        public Task<GenerateTokenResponse> GenerateToken(GenerateTokenRequest request)
        {
            SymmetricSecurityKey symmetricSecurityKey = new SymmetricSecurityKey(Encoding.ASCII.GetBytes(configuration["AppSettings:Secret"]));

            var dateTimeNow = DateTime.UtcNow;

            JwtSecurityToken jwt = new JwtSecurityToken(
                    issuer: configuration["AppSettings:ValidIssuer"],
                    audience: configuration["AppSettings:ValidAudience"],
                    claims: new List<Claim> {
                        new Claim("username", request.User.Username),
                        new Claim("email", request.User.Email),
                        new Claim("name", request.User.Name),
                        new Claim("surname", request.User.Surname),
                        new Claim("phone", request.User.Phone),
                        new Claim("id", request.User.Id.ToString()),
                        new Claim("roles", JsonConvert.SerializeObject(request.User.Roles)),
                        new Claim("permissions", JsonConvert.SerializeObject(request.User.Permissions.Select(s => s.Id))),
                        new Claim("organizations", JsonConvert.SerializeObject(request.User.Organizations)),
                    },
                    notBefore: dateTimeNow,
                    expires: dateTimeNow.ToLocalTime().AddMinutes(Convert.ToInt32(configuration["AppSettings:TokenValidityInMinutes"])),
                    signingCredentials: new SigningCredentials(symmetricSecurityKey, SecurityAlgorithms.HmacSha256)
                );
                
            return Task.FromResult(new GenerateTokenResponse
            {
                Token = new JwtSecurityTokenHandler().WriteToken(jwt),
                TokenExpireDate = dateTimeNow.ToLocalTime().AddMinutes(Convert.ToInt32(configuration["AppSettings:TokenValidityInMinutes"])),
                RefreshToken = GenerateRefreshToken(),
                RefreshTokenExpireDate = dateTimeNow.AddDays(Convert.ToInt32(configuration["AppSettings:RefreshTokenValidityInDays"]))

        });
        }

        public Task<ClaimsPrincipal?> GetPrincipalFromExpiredToken(string? token)
        {
            var tokenValidationParameters = new TokenValidationParameters
            {
                ValidateAudience = false,
                ValidateIssuer = false,
                ValidateIssuerSigningKey = true,
                IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(configuration["AppSettings:Secret"])),
                ValidateLifetime = false
            };

            var tokenHandler = new JwtSecurityTokenHandler();
            var principal = tokenHandler.ValidateToken(token, tokenValidationParameters, out SecurityToken securityToken);
            if (securityToken is not JwtSecurityToken jwtSecurityToken || !jwtSecurityToken.Header.Alg.Equals(SecurityAlgorithms.HmacSha256, StringComparison.InvariantCultureIgnoreCase))
                throw new SecurityTokenException("Invalid token");

            return Task.FromResult(principal);

        }
        private static string GenerateRefreshToken()
        {
            var randomNumber = new byte[64];
            using var rng = RandomNumberGenerator.Create();
            rng.GetBytes(randomNumber);
            return Convert.ToBase64String(randomNumber);
        }

    }
}
