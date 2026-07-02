using MailKit.Net.Smtp;
using MailKit.Security;
using Microsoft.EntityFrameworkCore;
using MimeKit;
using System.Data;
using System.Security.Cryptography;
using System.Text;
using UserManagement.DbContexts;
using UserManagement.Entity;
using UserManagement.Interfaces;
using UserManagement.Model;

namespace UserManagement.Services
{
    public class AuthService : IAuthService
    {
        const int keySize = 64;
        const int iterations = 350000;
        HashAlgorithmName hashAlgorithm = HashAlgorithmName.SHA512;

        private readonly UserManagementContext _dbContext;
        private readonly ITokenService tokenService;
        private readonly MailSettings _mailSettings;

        public AuthService(UserManagementContext dbContext, ITokenService tokenService, MailSettings mailSettings)
        {
            _dbContext = dbContext;
            this.tokenService = tokenService;
            _mailSettings = mailSettings;
        }

        public async Task<Result<UserLoginResponse>> Login(UserLoginRequest request)
        {
            var result = new Result<UserLoginResponse>();

                try
                {
                    var user = await _dbContext.Users.Where(x => (request.Username == x.Username || request.Username == x.Email) && !x.IsDeleted)
                        .Select(s => new User()
                        {
                            Id = s.Id,
                            Name = s.Name,
                            Surname = s.Surname,
                            Username = s.Username,
                            Password = s.Password,
                            Salt = s.Salt,
                            Email = s.Email,
                            Phone = s.Phone,
                            Permissions = _dbContext.UserPermissions.Include(p => p.Permission).Where(x => !x.IsDeleted && x.UserId == s.Id).Select(p => p.Permission).ToList(),
                            Roles = _dbContext.UserRoles.Where(x => !x.IsDeleted && x.UserId == s.Id).Select(p => p.RoleId).ToList(),
                            Organizations = _dbContext.OrganizationUsers.Where(x => !x.IsDeleted && x.UserId == s.Id).Select(p => p.OrganizationId).ToList()
                        }).FirstOrDefaultAsync();

                    if(user != null)
                    {
                        var isSuccess = VerifyPassword(request.Password, user.Password, user.Salt);
                        if (isSuccess)
                        {
                            var generatedTokenInformation = await tokenService.GenerateToken(new GenerateTokenRequest { User = user });
                            await UpdateRefreshToken(user, generatedTokenInformation.RefreshToken, generatedTokenInformation.RefreshTokenExpireDate);

                            UserLoginResponse response = new UserLoginResponse();
                            response.AuthenticateResult = true;
                            response.AccessToken = generatedTokenInformation.Token;
                            //response.AccessTokenExpireDate = generatedTokenInformation.TokenExpireDate;
                            response.RefreshToken = generatedTokenInformation.RefreshToken;
                            //response.RefreshTokenExpireDate = generatedTokenInformation.RefreshTokenExpireDate;

                            result.SetData(response);
                            result.SetMessage("İşlem başarı ile gerçekleşti.");
                        }
                        else
                        {
                            result.SetIsSuccess(false);
                            result.SetMessage("Şifre hatalı.");
                        }
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Kullanıcı adı/e-posta hatalı.");
                    }

                }
                catch (Exception ex)
                {
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }

            return result;
        }

        public async Task<Result<UserLoginResponse>> RefreshToken(RefreshTokenRequest request)
        {
            var result = new Result<UserLoginResponse>();

            var principal = await tokenService.GetPrincipalFromExpiredToken(request.AccessToken);
            if (principal == null)
            {
                result.SetIsSuccess(false);
                result.SetMessage("Invalid access token or refresh token");
            }
            else
            {
                try
                {
                    var userId = principal.Claims.Where(x => x.Type == "id").Select(s => s.Value).FirstOrDefault();

                    var applicationUser = await _dbContext.ApplicationUsers.Include(i => i.User).Where(x => x.UserId == Convert.ToInt64(userId))
                    .FirstOrDefaultAsync();

                    if (applicationUser == null || applicationUser.RefreshToken != request.RefreshToken || applicationUser.RefreshTokenExpireDate <= DateTime.UtcNow)
                    {

                        result.SetIsSuccess(false);
                        result.SetMessage("Invalid access token or refresh token");
                    }
                    else
                    {
                        var user = await _dbContext.Users.Where(x => x.Id == applicationUser.User.Id && !x.IsDeleted)
                       .Select(s => new User()
                       {
                           Id = s.Id,
                           Name = s.Name,
                           Surname = s.Surname,
                           Username = s.Username,
                           Password = s.Password,
                           Salt = s.Salt,
                           Email = s.Email,
                           Phone = s.Phone,
                           Permissions = _dbContext.UserPermissions.Include(p => p.Permission).Where(x => !x.IsDeleted && x.UserId == s.Id).Select(p => p.Permission).ToList(),
                           Roles = _dbContext.UserRoles.Where(x => !x.IsDeleted && x.UserId == s.Id).Select(p => p.RoleId).ToList(),
                           Organizations = _dbContext.OrganizationUsers.Where(x => !x.IsDeleted && x.UserId == s.Id).Select(p => p.OrganizationId).ToList()
                       }).FirstOrDefaultAsync();

                        var generatedTokenInformation = await tokenService.GenerateToken(new GenerateTokenRequest { User = user });
                        await UpdateRefreshToken(applicationUser.User, generatedTokenInformation.RefreshToken, generatedTokenInformation.RefreshTokenExpireDate);

                        UserLoginResponse response = new UserLoginResponse();
                        response.AuthenticateResult = true;
                        response.AccessToken = generatedTokenInformation.Token;
                        //response.AccessTokenExpireDate = generatedTokenInformation.TokenExpireDate;
                        response.RefreshToken = generatedTokenInformation.RefreshToken;
                        //response.RefreshTokenExpireDate = generatedTokenInformation.RefreshTokenExpireDate;

                        result.SetData(response);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                }
                catch (Exception ex)
                {
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }


        private async Task UpdateRefreshToken(User user, string refreshToken, DateTime refreshTokenExpireDate)
        {
            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var applicationUser = await _dbContext.ApplicationUsers.Where(x => x.UserId == user.Id).FirstOrDefaultAsync();

                    if (applicationUser == null)
                    {
                        applicationUser = new ApplicationUser();
                        applicationUser.UserId = user.Id;
                        applicationUser.RefreshToken = refreshToken;
                        applicationUser.RefreshTokenExpireDate = refreshTokenExpireDate;
                        _dbContext.Add(applicationUser);
                    }
                    else
                    {
                        applicationUser.RefreshToken = refreshToken;
                        applicationUser.RefreshTokenExpireDate = refreshTokenExpireDate;
                    }

                    await _dbContext.SaveChangesAsync();
                    transaction.Commit();
                }
                catch (Exception ex)
                {
                    transaction.Rollback();
                }
            }
        }

        public async Task<Result<string>> ForgotPassword(ForgotPasswordRequest request)
        {
            var result = new Result<string>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var user = await _dbContext.Users.Where(x => x.Email == request.Email).FirstOrDefaultAsync();

                    if(user != null)
                    {
                        await SendResetPasswordLink(user.Email, "http://localhost:4200/auth/reset-password/" + user.Id);

                        result.SetData(request.Email);
                        result.SetIsSuccess(true);
                        result.SetMessage("Sıfırlama linki mail adresine gönderildi.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Kullanıcı adı/e-posta hatalı.");
                    }
                }
                catch (Exception ex)
                {
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<bool>> ResetPassword(ResetPasswordRequest request)
        {
            var result = new Result<bool>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var user = await _dbContext.Users.Where(x => x.Id == request.Id).FirstOrDefaultAsync();

                    if (user != null)
                    {
                        var hashedPassword = HashPasword(request.Password, out var salt);

                        user.Password = hashedPassword;
                        user.Salt = salt;

                        await _dbContext.SaveChangesAsync();

                        transaction.Commit();
                        result.SetData(true);
                        result.SetIsSuccess(true);
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Böyle bir kullanıcı bulunamadı.");
                    }
                }
                catch (Exception ex)
                {
                    transaction.Rollback();
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<bool>> ChangePassword(ChangePasswordRequest request)
        {
            var result = new Result<bool>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var user = await _dbContext.Users.Where(x => x.Id == request.Id).FirstOrDefaultAsync();

                    if (user != null)
                    {
                        var isSuccess = VerifyPassword(request.CurrentPassword, user.Password, user.Salt);
                        if (isSuccess)
                        {

                            var hashedPassword = HashPasword(request.Password, out var salt);

                            user.Password = hashedPassword;
                            user.Salt = salt;

                            await _dbContext.SaveChangesAsync();

                            transaction.Commit();
                            result.SetData(true);
                            result.SetIsSuccess(true);
                        }
                        else
                        {
                            result.SetIsSuccess(false);
                            result.SetMessage("Current password is incorrect.");
                        }
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Böyle bir kullanıcı bulunamadı.");
                    }
                }
                catch (Exception ex)
                {
                    transaction.Rollback();
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<User>> Register(User user)
        {
            var result = new Result<User>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    if (!_dbContext.Users.Where(x => x.Username == user.Username).Any())
                    {
                        var hashedPassword = HashPasword(user.Password, out var salt);

                        user.Password = hashedPassword;
                        user.Salt = salt;

                        _dbContext.Users.Add(user);
                        await _dbContext.SaveChangesAsync();

                        if (user.IsProducer)
                        {
                            UserRole ur = new UserRole();
                            ur.RoleId = 3;
                            ur.UserId = user.Id;
                            ur.IsDeleted = false;

                            _dbContext.Add(ur);
                            await _dbContext.SaveChangesAsync();

                            var rolePermissions = await _dbContext.RolePermissions.Where(x => x.RoleId == 3 && !x.IsDeleted).Select(s => s.PermissionId).ToListAsync();
                            foreach (var permission in rolePermissions)
                            {
                                UserPermission up = new UserPermission();
                                up.PermissionId = permission;
                                up.UserId = user.Id;
                                up.IsDeleted = false;

                                _dbContext.Add(up);
                                await _dbContext.SaveChangesAsync();
                            }
                        }
                        else
                        {
                            UserRole ur = new UserRole();
                            ur.RoleId = 4;
                            ur.UserId = user.Id;
                            ur.IsDeleted = false;

                            _dbContext.Add(ur);
                            await _dbContext.SaveChangesAsync();

                            var rolePermissions = await _dbContext.RolePermissions.Where(x => x.RoleId == 4 && !x.IsDeleted).Select(s => s.PermissionId).ToListAsync();
                            foreach (var permission in rolePermissions)
                            {
                                UserPermission up = new UserPermission();
                                up.PermissionId = permission;
                                up.UserId = user.Id;
                                up.IsDeleted = false;

                                _dbContext.Add(up);
                                await _dbContext.SaveChangesAsync();
                            }
                        }

                        transaction.Commit();

                        result.SetData(user);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Aynı kullanıcı ismine sahip başka bir kullanıcı bulunmaktadır.");
                    }

                }
                catch (Exception ex)
                {
                    transaction.Rollback();

                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        
        }

        private async Task SendResetPasswordLink(string email, string link)
        {
            var emailMessage = new MimeMessage();
            emailMessage.Sender = MailboxAddress.Parse(_mailSettings.Mail);
            emailMessage.From.Add(MailboxAddress.Parse(_mailSettings.Mail));
            emailMessage.To.Add(MailboxAddress.Parse(email));
            emailMessage.Subject = "Reset Password Link";
            emailMessage.Body = new TextPart(MimeKit.Text.TextFormat.Text) { Text = "Şifrenizi sıfırlamak için lütfen aşağıdaki linke tıklayınız.\n" + link};

            using var smtp = new SmtpClient();
            smtp.Connect(_mailSettings.Host, _mailSettings.Port, SecureSocketOptions.SslOnConnect);
            smtp.Authenticate(_mailSettings.Mail, _mailSettings.Password);
            await smtp.SendAsync(emailMessage);
            smtp.Disconnect(true);
        }

        private bool VerifyPassword(string password, string hash, byte[] salt)
        {
            var hashToCompare = Rfc2898DeriveBytes.Pbkdf2(password, salt, iterations, hashAlgorithm, keySize);
            return CryptographicOperations.FixedTimeEquals(hashToCompare, Convert.FromHexString(hash));
        }

        private string HashPasword(string password, out byte[] salt)
        {
            salt = RandomNumberGenerator.GetBytes(keySize);
            var hash = Rfc2898DeriveBytes.Pbkdf2(
                Encoding.UTF8.GetBytes(password),
                salt,
                iterations,
                hashAlgorithm,
                keySize);
            return Convert.ToHexString(hash);
        }
    }
}
