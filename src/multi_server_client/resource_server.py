from typing import List
from urllib.parse import unquote
from uuid import UUID

from mcp.server.fastmcp import FastMCP


try:
    from .inventory_db import (
        DatabaseSchema,
        EnrichedInventoryItem,
        InventoryOverview,
        InventoryStatistics,
        ItemCategory,
        ItemStatus,
        db,
    )
except ImportError:
    from src.multi_server_client.inventory_db import (
        DatabaseSchema,
        EnrichedInventoryItem,
        InventoryOverview,
        InventoryStatistics,
        ItemCategory,
        ItemStatus,
        db,
    )


mcp = FastMCP("Inventory Management")


@mcp.resource("inventory://overview")
def get_inventory_overview() -> InventoryOverview:
    """Returns comprehensive inventory overview."""
    total_items = len(db.list_enriched_items())
    total_value = db.get_inventory_value()
    low_stock_items = len(db.get_low_stock_items())
    category_stats = db.get_category_stats()

    return InventoryOverview(
        total_items=total_items,
        total_value=total_value,
        low_stock_items=low_stock_items,
        category_stats=category_stats,
    )


@mcp.resource("inventory://items")
def get_all_items() -> List[EnrichedInventoryItem]:
    """Returns list of all inventory items."""
    return db.list_enriched_items()


@mcp.resource("inventory://item/{item_id}")
def get_item_details(item_id: str) -> EnrichedInventoryItem | str:
    """Get detailed inventory item information by UUID.

    Parameter: item_id (UUID string) - Use UUIDs from inventory://items resource.
    Example: inventory://item/e6ec9f9f-19a3-49bd-8efe-97aca565afb0
    Returns: Complete item details including product info, pricing, stock levels, and supplier data."""
    try:
        uuid_id = UUID(item_id)
        item = db.get_enriched_item(uuid_id)

        if not item:
            return f"Item with ID {item_id} not found."

        return item

    except ValueError:
        return f"Invalid item ID format: {item_id}"


@mcp.resource("inventory://item/name/{item_name}")
def get_item_by_name(item_name: str) -> EnrichedInventoryItem | str:
    """Find inventory item by exact product name.

    Parameter: item_name (string) - Exact product name (case-sensitive).
    Note: Names with spaces should be URL-encoded (e.g., %20 for spaces).
    Examples:
    - inventory://item/name/Premium%20Coffee%20Beans
    - inventory://item/name/Earl%20Grey%20Tea
    - inventory://item/name/Chocolate%20Chip%20Cookies
    Returns: Complete item details if name matches exactly."""
    # URL decode the item name to handle spaces and special characters
    decoded_name = unquote(item_name)
    item = db.get_enriched_item_by_name(decoded_name)

    if not item:
        return f"Item '{decoded_name}' not found."

    return item


@mcp.resource("inventory://category/{category}")
def get_items_by_category(category: str) -> List[EnrichedInventoryItem] | str:
    """Get all inventory items in a specific category.

    Parameter: category (string) - Valid categories are:
    - beverages (coffee, tea, drinks)
    - food (cookies, snacks, consumables)
    - electronics (headphones, gadgets)
    - books (guides, manuals, literature)
    - clothing, home_garden, office_supplies, other

    Examples: inventory://category/beverages, inventory://category/electronics
    Returns: List of all items in the specified category."""
    try:
        cat_enum = ItemCategory(category.lower())
        items = db.list_enriched_items(category=cat_enum)

        if not items:
            return f"No items found in category '{category.title()}'."

        return items

    except ValueError:
        valid_categories = [cat.value for cat in ItemCategory]
        return f"Invalid category. Valid categories: {', '.join(valid_categories)}"


@mcp.resource("inventory://low-stock")
def get_low_stock_items() -> List[EnrichedInventoryItem] | str:
    """Returns items that need to be reordered."""
    items = db.get_low_stock_items()

    if not items:
        return "✅ All items are adequately stocked!"

    return items


@mcp.resource("inventory://search/{query}")
def search_inventory(query: str) -> List[EnrichedInventoryItem] | str:
    """Search inventory by keyword in name, description, or SKU.

    Parameter: query (string) - Search term to match against:
    - Product names (e.g., 'coffee', 'bluetooth', 'python')
    - Descriptions (e.g., 'wireless', 'high-quality', 'fresh')
    - SKUs (e.g., 'COF-001', 'ELEC-001', 'BOOK-001')
    Note: Queries with spaces should be URL-encoded (e.g., %20 for spaces).

    Examples:
    - inventory://search/coffee (finds coffee-related items)
    - inventory://search/wireless (finds wireless products)
    - inventory://search/chip%20cookies (finds items with "chip cookies")
    Returns: List of matching items, sorted by name."""
    # URL decode the query to handle spaces and special characters
    decoded_query = unquote(query)
    items = db.search_enriched_items(decoded_query)

    if not items:
        return f"No items found matching '{decoded_query}'."

    return items


@mcp.resource("inventory://database-schema")
def get_inventory_database_schema() -> DatabaseSchema:
    """Returns the complete database schema definition."""

    # Define all entities with their field types
    entities = {
        "Supplier": {
            "id": "str (Primary Key)",
            "name": "str",
            "contact_email": "Optional[str]",
            "contact_phone": "Optional[str]",
            "address": "Optional[str]",
            "created_at": "datetime",
            "updated_at": "datetime",
        },
        "Product": {
            "id": "UUID (Primary Key)",
            "name": "str",
            "description": "Optional[str]",
            "category": "ItemCategory (Enum)",
            "sku": "Optional[str]",
            "barcode": "Optional[str]",
            "weight": "Optional[Decimal]",
            "dimensions": "Optional[str]",
            "created_at": "datetime",
            "updated_at": "datetime",
        },
        "SupplierProduct": {
            "id": "UUID (Primary Key)",
            "product_id": "UUID (Foreign Key → Product.id)",
            "supplier_id": "str (Foreign Key → Supplier.id)",
            "supplier_part_number": "Optional[str]",
            "cost": "Optional[Decimal]",
            "lead_time_days": "Optional[int]",
            "minimum_order_quantity": "Optional[int]",
            "is_primary_supplier": "bool",
            "created_at": "datetime",
            "updated_at": "datetime",
        },
        "InventoryItem": {
            "id": "UUID (Primary Key)",
            "product_id": "UUID (Foreign Key → Product.id)",
            "location_id": "Optional[str]",
            "status": "ItemStatus (Enum)",
            "price": "Decimal",
            "quantity_on_hand": "int",
            "quantity_reserved": "int",
            "quantity_allocated": "int",
            "reorder_point": "int",
            "max_stock": "int",
            "created_at": "datetime",
            "updated_at": "datetime",
            "last_restocked_at": "Optional[datetime]",
            "last_counted_at": "Optional[datetime]",
        },
        "EnrichedInventoryItem": {
            "description": "View model combining data from all entities",
            "note": "Used for API responses - not stored in database",
        },
    }

    # Define relationships between entities
    relationships = [
        {
            "from": "SupplierProduct",
            "to": "Supplier",
            "type": "Many-to-One",
            "foreign_key": "supplier_id → Supplier.id",
            "description": "Each supplier-product relationship belongs to one supplier",
        },
        {
            "from": "SupplierProduct",
            "to": "Product",
            "type": "Many-to-One",
            "foreign_key": "product_id → Product.id",
            "description": "Each supplier-product relationship belongs to one product",
        },
        {
            "from": "InventoryItem",
            "to": "Product",
            "type": "Many-to-One",
            "foreign_key": "product_id → Product.id",
            "description": "Each inventory item tracks stock for one product",
        },
        {
            "from": "Supplier",
            "to": "Product",
            "type": "Many-to-Many",
            "through": "SupplierProduct",
            "description": "Suppliers can supply multiple products, products can have multiple suppliers",
        },
    ]

    # Define database indexes for performance
    indexes = {
        "primary_keys": ["Supplier.id", "Product.id", "SupplierProduct.id", "InventoryItem.id"],
        "foreign_key_indexes": [
            "SupplierProduct.product_id",
            "SupplierProduct.supplier_id",
            "InventoryItem.product_id",
        ],
        "business_logic_indexes": [
            "Product.name",
            "Product.sku",
            "Product.category",
            "InventoryItem.status",
            "InventoryItem.needs_reorder (computed)",
        ],
    }

    return DatabaseSchema(
        entities=entities,
        relationships=relationships,
        indexes=indexes,
        normalization_level="Third Normal Form (3NF)",
        description=(
            "Fully normalized inventory management database schema. Eliminates all redundancy by separating "
            "concerns into distinct entities: Supplier (vendor data), Product (item master data), "
            "SupplierProduct (supplier-product relationships with pricing), and InventoryItem (stock tracking). "
            "The EnrichedInventoryItem model provides a denormalized view for API consumption, combining data "
            "from all entities."
        ),
    )


@mcp.resource("inventory://stats")
def get_inventory_statistics() -> InventoryStatistics:
    """Returns comprehensive inventory statistics."""
    total_items = len(db.list_enriched_items())
    total_value = db.get_inventory_value()
    category_stats = db.get_category_stats()
    low_stock_count = len(db.get_low_stock_items())

    # Calculate additional stats
    active_items = len(db.list_enriched_items(status=ItemStatus.ACTIVE))
    all_items = db.list_enriched_items()
    out_of_stock = len([item for item in all_items if item.quantity_on_hand == 0])

    # Calculate category percentages
    category_percentages = {
        category: (count / total_items * 100) if total_items > 0 else 0 for category, count in category_stats.items()
    }

    return InventoryStatistics(
        total_items=total_items,
        active_items=active_items,
        total_value=total_value,
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock,
        category_stats=category_stats,
        category_percentages=category_percentages,
    )


# Legacy endpoints for backward compatibility
@mcp.resource("inventory://{inventory_name}/id")
def get_inventory_id_from_inventory_name(inventory_name: str) -> str:
    """Get UUID identifier for an item by its exact product name.

    Parameter: inventory_name (string) - Exact product name (case-sensitive).
    Note: Names with spaces should be URL-encoded (e.g., %20 for spaces).
    Available names: Premium Coffee Beans, Earl Grey Tea, Chocolate Chip Cookies,
    Wireless Bluetooth Headphones, Python Programming Guide

    Examples:
    - inventory://Premium%20Coffee%20Beans/id
    - inventory://Chocolate%20Chip%20Cookies/id
    Returns: UUID string that can be used in other resource templates.
    Use this to get IDs for the inventory://item/{item_id} template."""
    # URL decode the inventory name to handle spaces and special characters
    decoded_name = unquote(inventory_name)
    item = db.get_enriched_item_by_name(decoded_name)
    if item:
        return str(item.id)
    return f"Item '{decoded_name}' not found"


@mcp.resource("inventory://{inventory_id}/price")
def get_inventory_price_from_inventory_id(inventory_id: str) -> str:
    """Get current selling price for an item by UUID or name.

    Parameter: inventory_id (string) - Either:
    - UUID from inventory://items resource
    - Exact product name (fallback for compatibility)

    Examples:
    - inventory://e6ec9f9f-19a3-49bd-8efe-97aca565afb0/price
    - inventory://Premium Coffee Beans/price (legacy)

    Returns: Current selling price as decimal string (e.g., '12.99').
    For cost analysis, use full item details from inventory://item/{item_id}."""
    try:
        uuid_id = UUID(inventory_id)
        item = db.get_enriched_item(uuid_id)
        if item:
            return str(item.price)
        return f"Item with ID {inventory_id} not found"
    except ValueError:
        # Try to find by name for backward compatibility (URL decode for spaces)
        decoded_name = unquote(inventory_id)
        item = db.get_enriched_item_by_name(decoded_name)
        if item:
            return str(item.price)
        return f"Invalid ID format or item not found: {decoded_name}"


@mcp.resource("inventory://templates")
def get_available_templates() -> str:
    """List all available resource templates with examples and current item IDs.

    This resource helps Claude understand what templates are available and shows
    current valid values that can be used in the templates.
    """
    # Get current items for examples
    items = db.list_enriched_items()
    if not items:
        return "No inventory items available"

    sample_item = items[0]
    sample_name = sample_item.name
    sample_id = str(sample_item.id)

    template_info = f"""
AVAILABLE RESOURCE TEMPLATES:

1. Get item by ID:
   Template: inventory://item/{{item_id}}
   Example: inventory://item/{sample_id}
   Description: Get detailed item info by UUID from inventory://items

2. Get item by name:
   Template: inventory://item/name/{{item_name}}
   Example: inventory://item/name/{sample_name}
   Description: Get item info by exact product name

3. Get items by category:
   Template: inventory://category/{{category}}
   Examples: inventory://category/beverages, inventory://category/electronics
   Valid categories: beverages, food, electronics, books, clothing, home_garden, office_supplies, other

4. Search items:
   Template: inventory://search/{{query}}
   Examples: inventory://search/coffee, inventory://search/wireless, inventory://search/COF-001

5. Get item ID by name (legacy):
   Template: inventory://{{inventory_name}}/id
   Example: inventory://{sample_name}/id

6. Get item price by ID (legacy):
   Template: inventory://{{inventory_id}}/price
   Example: inventory://{sample_id}/price

CURRENT AVAILABLE ITEMS:
{chr(10).join(f'- {item.name} (ID: {item.id})' for item in items[:5])}
{'...' if len(items) > 5 else ''}

To use templates, replace {{parameter}} with actual values from the examples above.
"""
    return template_info.strip()


if __name__ == "__main__":
    print("Starting MCP Resource Server...")
    mcp.run()
