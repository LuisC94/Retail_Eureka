using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;
using Newtonsoft.Json;
using System.Data;
using System.IdentityModel.Tokens.Jwt;
using System.Net.Http.Headers;
using System.Security;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using UserManagement.DbContexts;
using UserManagement.Entity;
using UserManagement.Interfaces;
using UserManagement.Model;

namespace UserManagement.Services
{
    public class UserService : IUserService
    {
        const int keySize = 64;
        const int iterations = 350000;
        HashAlgorithmName hashAlgorithm = HashAlgorithmName.SHA512;

        private readonly UserManagementContext _dbContext;

        private readonly IConfiguration configuration;


        public UserService(UserManagementContext dbContext, IConfiguration configuration)
        {
            _dbContext = dbContext;
            this.configuration = configuration;
        }

        public async Task<Result<PagingResult<PagedList<User>>>> Paginate(PagingParameter pagingParameter)
        {
            var result = new Result<PagingResult<PagedList<User>>>();

            string lowerFilterText = string.IsNullOrEmpty(pagingParameter.FilterText) ? null : pagingParameter.FilterText.ToLower();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var queryable = _dbContext.Users
                        .Where(x => (String.IsNullOrEmpty(lowerFilterText) || (x.Name.ToLower().Contains(lowerFilterText)) || x.Surname.ToLower().Contains(lowerFilterText)))
                        .Select(s => new User()
                    {
                        Id = s.Id,
                        Name = s.Name,
                        Surname = s.Surname,
                        Username = s.Username,
                        IsDeleted = s.IsDeleted,
                        Email = s.Email,
                        Phone = s.Phone,
                        IsSystemData = s.IsSystemData,
                        Permissions = _dbContext.UserPermissions.Include(p => p.Permission).Where(x => !x.IsDeleted && x.UserId == s.Id).Select(p => p.Permission).ToList(),
                        Roles = _dbContext.UserRoles.Where(x => !x.IsDeleted && x.UserId == s.Id).Select(p => p.RoleId).ToList(),
                        Organizations = _dbContext.OrganizationUsers.Where(x => !x.IsDeleted && x.UserId == s.Id).Select(p => p.OrganizationId).ToList()
                    });

                    var pagination = PagedList<User>.ToPagedList(queryable, pagingParameter.PageNumber, pagingParameter.PageSize);

                    result.SetData(new PagingResult<PagedList<User>>()
                    {
                        Items = pagination,
                        TotalCount = pagination.TotalCount,
                    });

                    result.SetMessage("İşlem başarı ile gerçekleşti.");
                }
                catch (Exception ex)
                {
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<List<User>>> GetUsers()
        {
            var result = new Result<List<User>>();
            
            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var data = await _dbContext.Users.Where(x => !x.IsDeleted).ToListAsync();

                    result.SetData(data);
                    result.SetMessage("İşlem başarı ile gerçekleşti.");
                }
                catch (Exception ex)
                {
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<User>> Save(User user)
        {
            var result = new Result<User>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {

                    if(!_dbContext.Users.Where(x => x.Username == user.Username).Any())
                    {
                        var hashedPassword = HashPasword(user.Password, out var salt);

                        user.Password = hashedPassword;
                        user.Salt = salt;

                        _dbContext.Users.Add(user);
                        await _dbContext.SaveChangesAsync();

                        foreach (var role in user.Roles)
                        {
                            UserRole ur = new UserRole();
                            ur.RoleId = role;
                            ur.UserId = user.Id;
                            ur.IsDeleted = false;

                            _dbContext.Add(ur);
                            await _dbContext.SaveChangesAsync();

                            var rolePerms = await _dbContext.RolePermissions.Include(x => x.Permission).Where(x => x.RoleId == role).Select(s => s.Permission).ToListAsync();
                            user.Permissions.AddRange(rolePerms);
                        }

                        foreach (var permission in user.Permissions)
                        {
                            UserPermission up = new UserPermission();
                            up.PermissionId = permission.Id;
                            up.UserId = user.Id;
                            up.IsDeleted = false;

                            _dbContext.Add(up);
                            await _dbContext.SaveChangesAsync();
                        }

                        foreach (var organization in user.Organizations)
                        {
                            OrganizationUser ou = new OrganizationUser();
                            ou.OrganizationId = organization;
                            ou.UserId = user.Id;
                            ou.IsDeleted = false;

                            _dbContext.Add(ou);
                            await _dbContext.SaveChangesAsync();
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

        public async Task<Result<User>> Update(User user)
        {
            var result = new Result<User>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var oldUser = await _dbContext.Users.Where(x => x.Id == user.Id).FirstOrDefaultAsync();
                    if(oldUser != null) 
                    { 
                        oldUser.Surname = user.Surname;
                        oldUser.Name = user.Name;
                        oldUser.Email = user.Email;
                        oldUser.Phone = user.Phone;
                        oldUser.Username = user.Username;
                        oldUser.FileId = user.FileId;

                        var roles = await _dbContext.UserRoles.Where(x => x.UserId == user.Id).ToListAsync();
                        _dbContext.UserRoles.RemoveRange(roles);

                        var permissions = await _dbContext.UserPermissions.Where(x => x.UserId == user.Id).ToListAsync();
                        _dbContext.UserPermissions.RemoveRange(permissions);

                        var organizations = await _dbContext.OrganizationUsers.Where(x => x.UserId == user.Id).ToListAsync();
                        _dbContext.OrganizationUsers.RemoveRange(organizations);
                        await _dbContext.SaveChangesAsync();

                        foreach (var role in user.Roles)
                        {
                            UserRole ur = new UserRole();
                            ur.RoleId = role;
                            ur.UserId = user.Id;
                            ur.IsDeleted = false;

                            _dbContext.Add(ur);
                            await _dbContext.SaveChangesAsync();

                            var rolePerms = await _dbContext.RolePermissions.Include(x => x.Permission).Where(x => x.RoleId == role).Select(s => s.Permission).ToListAsync();
                            user.Permissions.AddRange(rolePerms);
                        }

                        foreach (var permission in user.Permissions)
                        {
                            UserPermission up = new UserPermission();
                            up.PermissionId = permission.Id;
                            up.UserId = user.Id;
                            up.IsDeleted = false;

                            _dbContext.Add(up);
                            await _dbContext.SaveChangesAsync();
                        }

                        foreach (var organization in user.Organizations)
                        {
                            OrganizationUser ou = new OrganizationUser();
                            ou.OrganizationId = organization;
                            ou.UserId = user.Id;
                            ou.IsDeleted = false;

                            _dbContext.Add(ou);
                            await _dbContext.SaveChangesAsync();
                        }

                        transaction.Commit();

                        result.SetData(user);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Böyle bir kayıt bulunmamaktadır.");
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

        public async Task<Result<User>> Delete(long id)
        {
            var result = new Result<User>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var oldUser = await _dbContext.Users.Where(x => x.Id == id && !x.IsDeleted).FirstOrDefaultAsync();
                    if (oldUser != null)
                    {
                        oldUser.IsDeleted = true;

                        var roles = await _dbContext.UserRoles.Where(x => x.UserId == oldUser.Id).ToListAsync();
                        _dbContext.UserRoles.RemoveRange(roles);

                        var permissions = await _dbContext.UserPermissions.Where(x => x.UserId == oldUser.Id).ToListAsync();
                        _dbContext.UserPermissions.RemoveRange(permissions);

                        var organizations = await _dbContext.OrganizationUsers.Where(x => x.UserId == oldUser.Id).ToListAsync();
                        _dbContext.OrganizationUsers.RemoveRange(organizations);

                        await _dbContext.SaveChangesAsync();
                        transaction.Commit();

                        result.SetData(oldUser);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Böyle bir kayıt bulunmamaktadır.");
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

        public async Task<Result<User>> GetById(long id, string token)
        {
            var result = new Result<User>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var user = await _dbContext.Users.Where(x => x.Id == id && !x.IsDeleted).FirstOrDefaultAsync();
                    if (user != null)
                    {
                        user.Password = null;
                        user.Salt = null;
                        user.Roles = await _dbContext.UserRoles.Where(x => x.UserId == id && !x.IsDeleted).Select(s => s.RoleId).ToListAsync();
                        user.Organizations = await _dbContext.OrganizationUsers.Where(x => x.UserId == id && !x.IsDeleted).Select(s => s.OrganizationId).ToListAsync();

                        if (user.FileId.HasValue)
                        {
                            user.FileResult = await GetFileResult(user.FileId.Value, token);
                        }

                        result.SetData(user);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Böyle bir kayıt bulunmamaktadır.");
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

        public async Task<Result<UserAddress>> GetUserAddressById(long id)
        {
            var result = new Result<UserAddress>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var userAddress = await _dbContext.UserAddresses.Where(x => x.Id == id && !x.IsDeleted).FirstOrDefaultAsync();
                    if (userAddress != null)
                    {
                        result.SetData(userAddress);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Böyle bir kayıt bulunmamaktadır.");
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


        public async Task<Result<UserAddress>> UserAddressSave(UserAddress userAddress)
        {
            var result = new Result<UserAddress>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    if (!_dbContext.UserAddresses.Where(x => (x.AddressHeader == userAddress.AddressHeader) && !x.IsDeleted).Any())
                    {
                        _dbContext.Add(userAddress);
                        await _dbContext.SaveChangesAsync();
                        transaction.Commit();

                        result.SetData(userAddress);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Aynı isim veya kodla tanımlı bir yetki bulunmaktadır.");
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

        public async Task<Result<UserAddress>> UserAddressUpdate(UserAddress userAddress)
        {
            var result = new Result<UserAddress>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var oldAddress = await _dbContext.UserAddresses.Where(x => x.Id == userAddress.Id && !x.IsDeleted).FirstOrDefaultAsync();

                    if (oldAddress != null)
                    {
                        if (!_dbContext.UserAddresses.Where(x => x.Id != oldAddress.Id && (x.AddressHeader == userAddress.AddressHeader) && !x.IsDeleted).Any())
                        {
                            oldAddress.Name = userAddress.Name;
                            oldAddress.Surname = userAddress.Surname;
                            oldAddress.Phone = userAddress.Phone;
                            oldAddress.Country = userAddress.Country;
                            oldAddress.City = userAddress.City;
                            oldAddress.District = userAddress.District;
                            oldAddress.Address = userAddress.Address;
                            oldAddress.AddressHeader = userAddress.AddressHeader;
                            oldAddress.InvoiceType = userAddress.InvoiceType;
                            oldAddress.VKN = userAddress.VKN;
                            oldAddress.VergiDairesi = userAddress.VergiDairesi;
                            oldAddress.FirmaAdi = userAddress.FirmaAdi;

                            await _dbContext.SaveChangesAsync();
                            transaction.Commit();

                            result.SetData(userAddress);
                            result.SetMessage("İşlem başarı ile gerçekleşti.");
                        }
                        else
                        {
                            result.SetIsSuccess(false);
                            result.SetMessage("Aynı başlıkla tanımlı bir adres bulunmaktadır.");
                        }
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Böyle bir kayıt bulunmamaktadır.");
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

        public async Task<Result<List<UserAddress>>> GetUserAddresses(long userId)
        {
            var result = new Result<List<UserAddress>>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var data = await _dbContext.UserAddresses.Where(x => x.UserId == userId && !x.IsDeleted).ToListAsync();

                    result.SetData(data);
                    result.SetMessage("İşlem başarı ile gerçekleşti.");
                }
                catch (Exception ex)
                {
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<UserAddress>> UserAddressDelete(long id)
        {
            var result = new Result<UserAddress>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var oldAddress = await _dbContext.UserAddresses.Where(x => x.Id == id && !x.IsDeleted).FirstOrDefaultAsync();
                    if (oldAddress != null)
                    {
                        oldAddress.IsDeleted = true;

                        await _dbContext.SaveChangesAsync();
                        transaction.Commit();

                        result.SetData(oldAddress);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Böyle bir kayıt bulunmamaktadır.");
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

        public async Task<Result<List<String>>> GetUserPermissions(string token)
        {
            var result = new Result<List<String>>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var principal = await GetPrincipalFromToken(token);
                    var userId = principal.Claims.Where(x => x.Type == "id").Select(s => s.Value).FirstOrDefault();

                    var roleIds = await _dbContext.UserRoles.Include(x => x.Role).Where(x => !x.Role.IsDeleted && x.UserId == Convert.ToInt64(userId)).Select(s => s.RoleId).ToListAsync();

                    var permissions = await _dbContext.RolePermissions.Include(x => x.Permission).Where(x => !x.Permission.IsDeleted && roleIds.Contains(x.RoleId))
                                                            .Select(s => s.Permission.Code).ToListAsync();

                    result.SetData(permissions);
                    result.SetMessage("Islem basari ile gerceklesti.");
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

        public async Task<Result<User>> UserAvatarUpdate(long id, long fileId)
        {
            var result = new Result<User>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var oldUser = await _dbContext.Users.Where(x => x.Id == id).FirstOrDefaultAsync();
                    if (oldUser != null)
                    {
                        oldUser.FileId = fileId;
                     
                        await _dbContext.SaveChangesAsync();
                        transaction.Commit();

                        result.SetData(oldUser);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Böyle bir kayıt bulunmamaktadır.");
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

        private Task<ClaimsPrincipal?> GetPrincipalFromToken(string? token)
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

        private async Task<FileContentResult> GetFileResult(long id, string token)
        {
            HttpClient client = new HttpClient();
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

            var response = await client.GetAsync(configuration["AppSettings:ApiUrl"] + "/api/File/" + id);

            if (response.IsSuccessStatusCode)
            {
                var responseStr = await response.Content.ReadAsStringAsync();

                if (!string.IsNullOrEmpty(responseStr))
                {
                    try
                    {
                        Result<Model.File> result = JsonConvert.DeserializeObject<Result<Model.File>>(responseStr);

                        if (result != null)
                        {
                            byte[] bytes = System.IO.File.ReadAllBytes(result.GetData().Path);
                            return new FileContentResult(bytes, result.GetData().ContentType);
                        }
                        else
                        {
                            return null;
                        }
                    }
                    catch (Exception ex)
                    {
                        return null;
                    }

                }
                else
                {
                    return null;
                }
            }
            else
            {
                return null;
            }

            return null;
        }

    }
}
