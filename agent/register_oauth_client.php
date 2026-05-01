<?php
/**
 * Register OAuth client for Clinical Co-Pilot Agent
 * Upload this to your OpenEMR public folder and visit it once
 * Then DELETE IT immediately for security
 */

$client_id = 'wRwKKiS5s_-f-GbXFz-z7ea_DvUbrcQ8Ez228Qs5JDc';
$client_secret = 'ymk9o1FUJzVUzCozNoKgW0gYp5mQk3fBInuM2yDVC5_73ImSKsJda4MOss_MnjBm5Jt0oA4Cm1hWevWcnS2I6g';
$client_name = 'Clinical Co-Pilot Agent';

// Connect to OpenEMR database (uses existing connection)
require_once(__DIR__ . '/../../sites/default/sqlconf.php');

$mysqli = new mysqli($host, $login, $pass, $dbase, $port);

if ($mysqli->connect_error) {
    die("Connection failed: " . $mysqli->connect_error);
}

// Insert OAuth client
$sql = "INSERT INTO oauth_clients (client_id, client_name, client_secret, is_confidential, grant_types, scope)
        VALUES (?, ?, ?, 1, 'client_credentials', 'patient/*.read user/*.read launch openid')";

$stmt = $mysqli->prepare($sql);
$stmt->bind_param("sss", $client_id, $client_name, $client_secret);

if ($stmt->execute()) {
    echo "✅ OAuth client registered successfully!<br>";
    echo "Client ID: " . htmlspecialchars($client_id) . "<br>";
    echo "<br><strong>⚠️ DELETE THIS FILE NOW FOR SECURITY!</strong>";
} else {
    echo "❌ Error: " . $stmt->error;
}

$stmt->close();
$mysqli->close();
?>
