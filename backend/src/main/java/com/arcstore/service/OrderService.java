package com.arcstore.service;

import com.arcstore.dto.TaxPreviewResponse;
import com.arcstore.dto.TaxRateResponse;
import com.arcstore.model.Order;
import com.arcstore.model.Product;
import com.arcstore.repository.OrderRepository;
import com.arcstore.repository.ProductRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import java.math.BigDecimal;

@Service
public class OrderService {

    @Autowired
    private ProductRepository productRepository;

    @Autowired
    private OrderRepository orderRepository;

    @Autowired
    private TaxService taxService;

    public Order placeOrder(Long productId, int quantity, double total) {
        productRepository.findById(productId)
                .orElseThrow(() -> new RuntimeException("Product not found: " + productId));
        return orderRepository.save(new Order(productId, quantity, total));
    }

    // Returns a breakdown of subtotal, tax, and total before the order is confirmed.
    public TaxPreviewResponse previewTax(Long productId, int quantity, String shippingState) {
        Product product = productRepository.findById(productId)
                .orElseThrow(() -> new RuntimeException("Product not found: " + productId));

        BigDecimal subtotal = BigDecimal.valueOf(product.getPrice()).multiply(BigDecimal.valueOf(quantity));

        // Call TaxService to get the tax rate for the product and shipping state
        TaxRateResponse taxResponse = taxService.getTaxRate(product.getTaxCode(), shippingState);
        if (taxResponse == null || taxResponse.getTaxRate() == null) {
            throw new IllegalStateException(
                "Tax rate unavailable for taxCode=" + product.getTaxCode() + ", state=" + shippingState);
        }
        double taxRate = taxResponse.getTaxRate();
        BigDecimal taxAmount = subtotal.multiply(BigDecimal.valueOf(taxRate));
        BigDecimal total = subtotal.add(taxAmount);

        return new TaxPreviewResponse(subtotal.doubleValue(), taxAmount.doubleValue(), total.doubleValue());
    }
}
