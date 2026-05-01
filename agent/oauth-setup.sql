-- Insert OAuth2 client for Clinical Co-Pilot Agent
-- Run this via Railway CLI

INSERT INTO oauth_clients (
    client_id,
    client_secret,
    client_name,
    client_role,
    is_confidential,
    grant_types,
    scope,
    redirect_uri,
    user_id
) VALUES (
    'wRwKKiS5s_-f-GbXFz-z7ea_DvUbrcQ8Ez228Qs5JDc',
    '$2y$10$abcdefghijklmnopqrstuv',  -- This will be updated in next step
    'Clinical Co-Pilot Agent',
    'user',
    1,
    'client_credentials',
    'patient/*.read user/*.read launch openid',
    '',
    NULL
);
