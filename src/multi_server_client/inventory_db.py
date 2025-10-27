from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import (
    Dict,
    List,
    Optional,
)
from uuid import (
    UUID,
    uuid4,
)

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


class ItemCategory(str, Enum):
    """Inventory item categories."""

    BEVERAGES = "beverages"
    FOOD = "food"
    ELECTRONICS = "electronics"
    BOOKS = "books"
    CLOTHING = "clothing"
    HOME_GARDEN = "home_garden"
    OFFICE_SUPPLIES = "office_supplies"
    OTHER = "other"


class ItemStatus(str, Enum):
    """Inventory item status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"


class InventoryOverview(BaseModel):
    """Inventory overview summary."""

    total_items: int
    total_value: Decimal
    low_stock_items: int
    category_stats: Dict[str, int]


class InventoryStatistics(BaseModel):
    """Comprehensive inventory statistics."""

    total_items: int
    active_items: int
    total_value: Decimal
    low_stock_count: int
    out_of_stock_count: int
    category_stats: Dict[str, int]
    category_percentages: Dict[str, float]


class DatabaseSchema(BaseModel):
    """Complete database schema definition."""

    entities: Dict[str, Dict[str, str]]
    relationships: List[Dict[str, str]]
    indexes: Dict[str, List[str]]
    normalization_level: str
    description: str


class Supplier(BaseModel):
    """Supplier entity."""

    id: str = Field(..., max_length=50, description="Supplier identifier")
    name: str = Field(..., min_length=1, max_length=100, description="Supplier name")
    contact_email: Optional[str] = Field(None, max_length=100, description="Contact email")
    contact_phone: Optional[str] = Field(None, max_length=20, description="Contact phone")
    address: Optional[str] = Field(None, max_length=200, description="Supplier address")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")


class Product(BaseModel):
    """Product master data entity."""

    id: UUID = Field(default_factory=uuid4, description="Unique product identifier")
    name: str = Field(..., min_length=1, max_length=100, description="Product name")
    description: Optional[str] = Field(None, max_length=500, description="Product description")
    category: ItemCategory = Field(..., description="Product category")
    sku: Optional[str] = Field(None, max_length=50, description="Stock Keeping Unit")
    barcode: Optional[str] = Field(None, max_length=50, description="Product barcode")
    weight: Optional[Decimal] = Field(None, gt=0, description="Weight in kg")
    dimensions: Optional[str] = Field(None, max_length=50, description="Dimensions (LxWxH)")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")

    @field_validator("updated_at")
    @classmethod
    def set_updated_at(cls, _: datetime) -> datetime:
        """Always update the updated_at timestamp."""
        return datetime.now()


class SupplierProduct(BaseModel):
    """Product-Supplier relationship entity."""

    id: UUID = Field(default_factory=uuid4, description="Unique relationship identifier")
    product_id: UUID = Field(..., description="Product identifier")
    supplier_id: str = Field(..., description="Supplier identifier")
    supplier_part_number: Optional[str] = Field(None, max_length=50, description="Supplier part number")
    cost: Optional[Decimal] = Field(None, ge=0, description="Supplier cost")
    lead_time_days: Optional[int] = Field(None, ge=0, description="Lead time in days")
    minimum_order_quantity: Optional[int] = Field(None, ge=1, description="Minimum order quantity")
    is_primary_supplier: bool = Field(default=False, description="Is primary supplier for this product")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")


class EnrichedInventoryItem(BaseModel):
    """Inventory item enriched with product and supplier data for API responses."""

    # Inventory data
    id: UUID
    status: ItemStatus
    price: Decimal
    quantity_on_hand: int
    quantity_reserved: int
    quantity_allocated: int
    available_quantity: int
    reorder_point: int
    max_stock: int
    needs_reorder: bool
    location_id: Optional[str]
    last_restocked_at: Optional[datetime]

    # Product data
    product_id: UUID
    name: str
    description: Optional[str]
    category: ItemCategory
    sku: Optional[str]
    barcode: Optional[str]
    weight: Optional[Decimal]
    dimensions: Optional[str]

    # Supplier data (from primary supplier)
    supplier_id: Optional[str]
    supplier_name: Optional[str]
    supplier_part_number: Optional[str]
    cost: Optional[Decimal]
    profit_margin: Optional[Decimal]

    # Timestamps
    created_at: datetime
    updated_at: datetime


class InventoryItem(BaseModel):
    """Normalized inventory item - focuses only on inventory tracking."""

    id: UUID = Field(default_factory=uuid4, description="Unique inventory item identifier")
    product_id: UUID = Field(..., description="Reference to product")
    location_id: Optional[str] = Field(None, max_length=50, description="Storage location identifier")
    status: ItemStatus = Field(default=ItemStatus.ACTIVE, description="Inventory status")

    # Pricing (current selling price)
    price: Decimal = Field(..., gt=0, description="Current selling price")

    # Inventory tracking
    quantity_on_hand: int = Field(default=0, ge=0, description="Current stock quantity")
    quantity_reserved: int = Field(default=0, ge=0, description="Reserved quantity")
    quantity_allocated: int = Field(default=0, ge=0, description="Allocated quantity")
    reorder_point: int = Field(default=10, ge=0, description="Reorder threshold")
    max_stock: int = Field(default=1000, gt=0, description="Maximum stock level")

    # Inventory timestamps
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    last_restocked_at: Optional[datetime] = Field(None, description="Last restock timestamp")
    last_counted_at: Optional[datetime] = Field(None, description="Last physical count timestamp")

    # Computed properties
    @property
    def available_quantity(self) -> int:
        """Calculate available quantity (on_hand - reserved - allocated)."""
        return max(0, self.quantity_on_hand - self.quantity_reserved - self.quantity_allocated)

    @property
    def needs_reorder(self) -> bool:
        """Check if item needs to be reordered."""
        return self.available_quantity <= self.reorder_point

    @field_validator("updated_at")
    @classmethod
    def set_updated_at(cls, _: datetime) -> datetime:
        """Always update the updated_at timestamp."""
        return datetime.now()


class InventoryDatabase:  # pylint: disable=too-many-instance-attributes
    """Normalized in-memory inventory database with CRUD operations."""

    def __init__(self) -> None:
        # Core entities
        self._suppliers: Dict[str, Supplier] = {}
        self._products: Dict[UUID, Product] = {}
        self._supplier_products: Dict[UUID, SupplierProduct] = {}
        self._inventory_items: Dict[UUID, InventoryItem] = {}

        # Indexes for fast lookups
        self._product_name_index: Dict[str, UUID] = {}
        self._product_sku_index: Dict[str, UUID] = {}
        self._category_index: Dict[ItemCategory, List[UUID]] = {cat: [] for cat in ItemCategory}
        self._supplier_product_index: Dict[UUID, List[UUID]] = {}  # product_id -> supplier_product ids
        self._inventory_product_index: Dict[UUID, UUID] = {}  # inventory_id -> product_id

    def add_supplier(self, supplier_obj: Supplier) -> Supplier:
        """Add a new supplier."""
        if supplier_obj.id in self._suppliers:
            raise ValueError(f"Supplier with ID '{supplier_obj.id}' already exists")

        self._suppliers[supplier_obj.id] = supplier_obj
        return supplier_obj

    def add_product(self, product_obj: Product) -> Product:
        """Add a new product."""
        # Check for duplicate names
        if product_obj.name.lower() in [name.lower() for name in self._product_name_index]:
            raise ValueError(f"Product with name '{product_obj.name}' already exists")

        # Check for duplicate SKUs
        if product_obj.sku and product_obj.sku in self._product_sku_index:
            raise ValueError(f"Product with SKU '{product_obj.sku}' already exists")

        # Add to main storage and indexes
        self._products[product_obj.id] = product_obj
        self._product_name_index[product_obj.name] = product_obj.id
        if product_obj.sku:
            self._product_sku_index[product_obj.sku] = product_obj.id
        self._category_index[product_obj.category].append(product_obj.id)
        self._supplier_product_index[product_obj.id] = []

        return product_obj

    def add_supplier_product(self, supplier_product_obj: SupplierProduct) -> SupplierProduct:
        """Add a supplier-product relationship."""
        if supplier_product_obj.product_id not in self._products:
            raise ValueError(f"Product with ID '{supplier_product_obj.product_id}' does not exist")

        if supplier_product_obj.supplier_id not in self._suppliers:
            raise ValueError(f"Supplier with ID '{supplier_product_obj.supplier_id}' does not exist")

        self._supplier_products[supplier_product_obj.id] = supplier_product_obj
        self._supplier_product_index[supplier_product_obj.product_id].append(supplier_product_obj.id)

        return supplier_product_obj

    def add_inventory_item(self, inventory_item_obj: InventoryItem) -> InventoryItem:
        """Add a new inventory item."""
        if inventory_item_obj.product_id not in self._products:
            raise ValueError(f"Product with ID '{inventory_item_obj.product_id}' does not exist")

        self._inventory_items[inventory_item_obj.id] = inventory_item_obj
        self._inventory_product_index[inventory_item_obj.id] = inventory_item_obj.product_id

        return inventory_item_obj

    def get_enriched_item(self, inventory_id: UUID) -> Optional[EnrichedInventoryItem]:
        """Get enriched inventory item with product and supplier data."""
        inventory_item_obj = self._inventory_items.get(inventory_id)
        if not inventory_item_obj:
            return None

        product_obj = self._products.get(inventory_item_obj.product_id)
        if not product_obj:
            return None

        # Get primary supplier information
        supplier_id = None
        supplier_name = None
        supplier_part_number = None
        cost = None

        supplier_product_ids = self._supplier_product_index.get(product_obj.id, [])
        for sp_id in supplier_product_ids:
            supplier_product_obj = self._supplier_products.get(sp_id)
            if supplier_product_obj and supplier_product_obj.is_primary_supplier:
                supplier_id = supplier_product_obj.supplier_id
                supplier_part_number = supplier_product_obj.supplier_part_number
                cost = supplier_product_obj.cost
                supplier_obj = self._suppliers.get(supplier_id)
                supplier_name = supplier_obj.name if supplier_obj else None
                break

        # Calculate profit margin
        profit_margin = None
        if cost and cost > 0:
            profit_margin = ((inventory_item_obj.price - cost) / cost) * 100

        return EnrichedInventoryItem(
            id=inventory_item_obj.id,
            status=inventory_item_obj.status,
            price=inventory_item_obj.price,
            quantity_on_hand=inventory_item_obj.quantity_on_hand,
            quantity_reserved=inventory_item_obj.quantity_reserved,
            quantity_allocated=inventory_item_obj.quantity_allocated,
            available_quantity=inventory_item_obj.available_quantity,
            reorder_point=inventory_item_obj.reorder_point,
            max_stock=inventory_item_obj.max_stock,
            needs_reorder=inventory_item_obj.needs_reorder,
            location_id=inventory_item_obj.location_id,
            last_restocked_at=inventory_item_obj.last_restocked_at,
            product_id=product_obj.id,
            name=product_obj.name,
            description=product_obj.description,
            category=product_obj.category,
            sku=product_obj.sku,
            barcode=product_obj.barcode,
            weight=product_obj.weight,
            dimensions=product_obj.dimensions,
            supplier_id=supplier_id,
            supplier_name=supplier_name,
            supplier_part_number=supplier_part_number,
            cost=cost,
            profit_margin=profit_margin,
            created_at=inventory_item_obj.created_at,
            updated_at=inventory_item_obj.updated_at,
        )

    def get_enriched_item_by_name(self, name: str) -> Optional[EnrichedInventoryItem]:
        """Get enriched inventory item by product name."""
        product_id = self._product_name_index.get(name)
        if not product_id:
            return None

        # Find inventory item for this product
        for inventory_id, inv_product_id in self._inventory_product_index.items():
            if inv_product_id == product_id:
                return self.get_enriched_item(inventory_id)

        return None

    def list_enriched_items(
        self,
        category: Optional[ItemCategory] = None,
        status: Optional[ItemStatus] = None,
        needs_reorder: Optional[bool] = None,
    ) -> List[EnrichedInventoryItem]:
        """List enriched inventory items with optional filters."""
        items = []

        for inventory_id in self._inventory_items:
            enriched_item = self.get_enriched_item(inventory_id)
            if enriched_item:
                items.append(enriched_item)

        if category:
            items = [item for item in items if item.category == category]

        if status:
            items = [item for item in items if item.status == status]

        if needs_reorder is not None:
            items = [item for item in items if item.needs_reorder == needs_reorder]

        return sorted(items, key=lambda x: x.name)

    def get_low_stock_items(self) -> List[EnrichedInventoryItem]:
        """Get enriched items that need to be reordered."""
        return [item for item in self.list_enriched_items() if item.needs_reorder]

    def get_inventory_value(self) -> Decimal:
        """Calculate total inventory value."""
        total = sum(item.price * item.quantity_on_hand for item in self._inventory_items.values())
        return Decimal(str(total))

    def get_category_stats(self) -> Dict[str, int]:
        """Get item count by category."""
        stats = {}
        for category in ItemCategory:
            count = 0
            for inventory_id in self._inventory_items:
                enriched_item = self.get_enriched_item(inventory_id)
                if enriched_item and enriched_item.category == category:
                    count += 1
            if count > 0:
                stats[category.value] = count
        return stats

    def search_enriched_items(self, query: str) -> List[EnrichedInventoryItem]:
        """Search enriched items by name, description, or SKU."""
        query_lower = query.lower()
        results = []

        for inventory_id in self._inventory_items:
            enriched_item = self.get_enriched_item(inventory_id)
            if not enriched_item:
                continue

            # Check if query matches name, description, or SKU
            name_match = query_lower in enriched_item.name.lower()
            desc_match = enriched_item.description and query_lower in enriched_item.description.lower()
            sku_match = enriched_item.sku and query_lower in enriched_item.sku.lower()

            if name_match or desc_match or sku_match:
                results.append(enriched_item)

        return sorted(results, key=lambda x: x.name)


# Initialize the database
db = InventoryDatabase()

# Initialize with normalized sample data
# Create sample suppliers
suppliers_data = [
    {"id": "SUP-001", "name": "Colombian Coffee Co.", "contact_email": "orders@colombiancoffee.com"},
    {"id": "SUP-002", "name": "Tea Imports Ltd.", "contact_email": "sales@teaimports.com"},
    {"id": "SUP-003", "name": "Local Bakery", "contact_phone": "555-0123"},
    {"id": "SUP-004", "name": "TechSupply Inc.", "contact_email": "wholesale@techsupply.com"},
    {"id": "SUP-005", "name": "Academic Publishers", "contact_email": "orders@academicpub.com"},
]

suppliers = [Supplier.model_validate(data) for data in suppliers_data]

for supplier in suppliers:
    db.add_supplier(supplier)
    print(f"Added supplier: {supplier.id} - {supplier.name}")

# Create sample products
products_data = [
    {
        "name": "Premium Coffee Beans",
        "description": "High-quality Arabica coffee beans from Colombia",
        "category": ItemCategory.BEVERAGES,
        "sku": "COF-001",
        "weight": Decimal("1.0"),
    },
    {
        "name": "Earl Grey Tea",
        "description": "Classic Earl Grey black tea with bergamot",
        "category": ItemCategory.BEVERAGES,
        "sku": "TEA-001",
    },
    {
        "name": "Chocolate Chip Cookies",
        "description": "Fresh baked chocolate chip cookies",
        "category": ItemCategory.FOOD,
        "sku": "COOK-001",
    },
    {
        "name": "Wireless Bluetooth Headphones",
        "description": "High-quality wireless headphones with noise cancellation",
        "category": ItemCategory.ELECTRONICS,
        "sku": "ELEC-001",
        "weight": Decimal("0.3"),
    },
    {
        "name": "Python Programming Guide",
        "description": "Comprehensive guide to Python programming",
        "category": ItemCategory.BOOKS,
        "sku": "BOOK-001",
    },
]

products = [Product.model_validate(data) for data in products_data]

for product in products:
    db.add_product(product)
    print(f"Added product: {product.id} - {product.name}")

# Create supplier-product relationships
supplier_products_data = [
    {
        "product_id": products[0].id,
        "supplier_id": "SUP-001",
        "cost": Decimal("6.50"),
        "is_primary_supplier": True,
        "lead_time_days": 14,
        "minimum_order_quantity": 50,
    },
    {
        "product_id": products[1].id,
        "supplier_id": "SUP-002",
        "cost": Decimal("4.25"),
        "is_primary_supplier": True,
        "lead_time_days": 7,
        "minimum_order_quantity": 25,
    },
    {
        "product_id": products[2].id,
        "supplier_id": "SUP-003",
        "cost": Decimal("2.50"),
        "is_primary_supplier": True,
        "lead_time_days": 1,
        "minimum_order_quantity": 12,
    },
    {
        "product_id": products[3].id,
        "supplier_id": "SUP-004",
        "cost": Decimal("120.00"),
        "is_primary_supplier": True,
        "lead_time_days": 21,
        "minimum_order_quantity": 5,
    },
    {
        "product_id": products[4].id,
        "supplier_id": "SUP-005",
        "cost": Decimal("25.00"),
        "is_primary_supplier": True,
        "lead_time_days": 10,
        "minimum_order_quantity": 10,
    },
]

supplier_products = [SupplierProduct.model_validate(data) for data in supplier_products_data]

for supplier_product in supplier_products:
    db.add_supplier_product(supplier_product)

# Create inventory items
inventory_items_data = [
    {"product_id": products[0].id, "price": Decimal("12.99"), "quantity_on_hand": 150, "reorder_point": 20},
    {"product_id": products[1].id, "price": Decimal("8.99"), "quantity_on_hand": 75, "reorder_point": 15},
    {"product_id": products[2].id, "price": Decimal("5.99"), "quantity_on_hand": 25, "reorder_point": 30},
    {"product_id": products[3].id, "price": Decimal("199.99"), "quantity_on_hand": 12, "reorder_point": 5},
    {"product_id": products[4].id, "price": Decimal("39.99"), "quantity_on_hand": 8, "reorder_point": 3},
]

inventory_items = [InventoryItem.model_validate(data) for data in inventory_items_data]

for inventory_item in inventory_items:
    db.add_inventory_item(inventory_item)
