// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract SupplyChain {
    
    // Identifica um interveniente
    struct Actor {
        string name;
        string role; // "Producer", "Transporter", "Retailer"
        bool isAuthorized;
    }
    
    // O Bloco Logístico (Snapshot de dados)
    struct BlockRecord {
        uint256 blockId;
        string batchId;        // Ex: "LOTE-101"
        string dataHash;       // O Hash SHA-256 do dossier JSON
        string previousHash;   // Hash do bloco anterior (para ligar a cadeia)
        address signer;        // Quem assinou
        uint256 timestamp;
        string eventType;      // "GENESIS", "TRANSPORT", "DELIVERY", "SALE"
    }

    mapping(address => Actor) public actors;
    mapping(string => BlockRecord[]) public chain; // batchId => Lista de Blocos

    event BlockCreated(string indexed batchId, uint256 blockIndex, address indexed signer, string eventType);

    constructor() {
        // O Deployer é o administrador inicial
        actors[msg.sender] = Actor("Admin", "Admin", true);
    }

    // 1. Autorizar utilizadores (Governança simplificada)
    function authorizeActor(address _actor, string memory _name, string memory _role) public {
        // Na versão final, exigir que msg.sender seja Admin
        actors[_actor] = Actor(_name, _role, true);
    }

    // 2. Criar um novo bloco na cadeia de um lote
    function addBlock(
        string memory _batchId, 
        string memory _dataHash, 
        string memory _eventType
    ) public {
        require(actors[msg.sender].isAuthorized, "Not authorized");

        BlockRecord[] storage batchChain = chain[_batchId];
        
        string memory _previousHash = "0";
        if (batchChain.length > 0) {
            // Se já existem blocos, o previousHash é o hash do último
            _previousHash = batchChain[batchChain.length - 1].dataHash;
        } else {
            // Se é o primeiro, tem de ser GENESIS
            //require(keccak256(bytes(_eventType)) == keccak256(bytes("GENESIS")), "First block must be GENESIS");
        }

        BlockRecord memory newBlock = BlockRecord({
            blockId: batchChain.length + 1,
            batchId: _batchId,
            dataHash: _dataHash,
            previousHash: _previousHash,
            signer: msg.sender,
            timestamp: block.timestamp,
            eventType: _eventType
        });

        batchChain.push(newBlock);

        emit BlockCreated(_batchId, batchChain.length, msg.sender, _eventType);
    }

    // 3. Ler a cadeia de um lote
    function getChain(string memory _batchId) public view returns (BlockRecord[] memory) {
        return chain[_batchId];
    }
}
