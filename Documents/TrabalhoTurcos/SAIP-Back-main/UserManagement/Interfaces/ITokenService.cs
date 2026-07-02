using System.Security.Claims;
using UserManagement.Model;

namespace UserManagement.Interfaces
{
    public interface ITokenService
    {
        Task<GenerateTokenResponse> GenerateToken(GenerateTokenRequest request);
        Task<ClaimsPrincipal?> GetPrincipalFromExpiredToken(string? token);
    }
}
